from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests,traceback
from market.services.rapidapi import call_api,BASE_URLs,HEADERS
import time
from .models import Ticker,TickerHistory
import pandas as pd

# Create your views here.
@api_view(["GET"])
def tickers(request):
    try:
        TYPES = ["STOCKS"]#In future you can just add this with paid plan,"ETFS", "MUTUALFUNDS", "CURRENCIES", "CRYPTOCURRENCIES", "COMMODITIES"
        max_api_index = int(request.GET.get("max_api_index", 10))  # default 10
        limit = int(request.GET.get("limit", 100))

        all_data = []
        skipped_calls = []

        def normalize_response(raw, market_type):
            """
            Normalize any API response into a clean schema:
            {
                symbol, name, price, net_change, pct_change, market_cap, market
            }
            """
            if not raw:
                return []

            # If wrapped inside "data" or "body"
            if isinstance(raw, dict):
                if "data" in raw and isinstance(raw["data"], list):
                    raw = raw["data"]
                elif "items" in raw and isinstance(raw["items"], list):
                    raw = raw["items"]
                elif "body" in raw and isinstance(raw["body"], list):
                    raw = raw["body"]
                else:
                    return []  # unexpected structure

            if not isinstance(raw, list):
                return []  # not usable

            normalized = []
            for row in raw:
                normalized.append({
                    "symbol": row.get("symbol") or row.get("ticker"),
                    "name": row.get("companyName") or row.get("name"),
                    "price": (
                        row.get("lastSalePrice")
                        or row.get("lastsale")
                        or row.get("price")
                    ),
                    "net_change": (
                        row.get("netChange")
                        or row.get("netchange")
                    ),
                    "pct_change": (
                        row.get("percentageChange")
                        or row.get("pctchange")
                    ),
                    "market_cap": row.get("marketCap"),
                    "market": market_type
                })
            return normalized

        for api_index in range(max_api_index):
            for t in TYPES:
                params = {"type": t, "limit": limit}
                try:
                    data = call_api("api/v2/markets/tickers", params=params, api_index=api_index)
                    print(f"Raw response for {t} @ index {api_index}: {str(data)[:200]}...")
                    normalized = normalize_response(data, t)

                    if not normalized:
                        skipped_calls.append({"type": t, "api_index": api_index, "reason": "Could not normalize"})
                        continue

                    all_data.extend(normalized)

                except Exception as e:
                    err_msg = str(e)
                    skipped_calls.append({"type": t, "api_index": api_index, "reason": err_msg})
                    print(f"Skipped API call for {t} @ index {api_index}: {err_msg}")
                    continue

                time.sleep(2)  # polite delay

        if not all_data:
            return Response({
                "status": "error",
                "message": "No valid data fetched",
                "skipped_calls": skipped_calls
            }, status=502)

        df = pd.DataFrame(all_data)
        print("Normalized DataFrame sample:")
        print(df.head())

        # Normalize and save to DB using field mapping
        field_mapping = {
            "symbol": "symbol",
            "name": "short_name",  # or long_name depending on API
            "companyName": "short_name",  # fallback for some APIs
            "lastsale": "regular_market_price",
            "lastSalePrice": "regular_market_price",
            "price": "regular_market_price",
            "netchange": "regular_market_change",
            "netChange": "regular_market_change",
            "pctchange": "regular_market_change_percent",
            "percentageChange": "regular_market_change_percent",
            "marketCap": "market_cap",
            "market": "market",
        }

        normalized_rows = []
        for _, row in df.iterrows():
            norm = {}
            for api_field, model_field in field_mapping.items():
                if api_field in row and pd.notna(row[api_field]):
                    value = row[api_field]

                    # Convert percentages / numbers to correct type
                    if model_field == "regular_market_price":
                        try:
                            value = float(str(value).replace("$", "").replace(",", ""))
                        except:
                            value = None
                    if model_field == "regular_market_change":
                        try:
                            value = float(str(value).replace("+", "").replace("-", "").replace(",", ""))
                            if str(row[api_field]).startswith("-"):
                                value = -value
                        except:
                            value = None
                    if model_field == "regular_market_change_percent":
                        try:
                            value = float(str(value).replace("%", "").replace(",", ""))
                        except:
                            value = None
                    if model_field == "market_cap":
                        try:
                            value = int(str(value).replace(",", ""))
                        except:
                            value = None

                    norm[model_field] = value

            # Only add if symbol and price are present
            if norm.get("symbol") and norm.get("regular_market_price") is not None:
                normalized_rows.append(Ticker(**norm))

        # Bulk insert, ignore duplicates
        if normalized_rows:
            Ticker.objects.bulk_create(normalized_rows, ignore_conflicts=True)

        return Response({
            "status": "success",
            "inserted_rows": len(normalized_rows),
            "sample": df.head().to_dict(orient="records"),
            "skipped_calls": skipped_calls
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)

@api_view(["GET"])
def newslist(request):
    try:
        region = request.GET.get("region", "US")
        snippet_count = int(request.GET.get("snippetCount", 10))

        all_articles = []
        errors = []

        def normalize_articles(raw):
            if not raw:
                return []

            if isinstance(raw, dict):
                if "data" in raw and isinstance(raw["data"], list):
                    raw = raw["data"]
                elif "items" in raw and isinstance(raw["items"], list):
                    raw = raw["items"]
                elif "body" in raw and isinstance(raw["body"], list):
                    raw = raw["body"]
                else:
                    return []  # unexpected structure

            if not isinstance(raw, list):
                return []

            normalized = []
            for item in raw:
                normalized.append({
                    "title": item.get("title"),
                    "link": item.get("link") or item.get("url"),
                    "source": item.get("source") or item.get("provider"),
                    "published_at": item.get("publishedAt") or item.get("pubDate"),
                    "snippet": item.get("snippet") or item.get("summary"),
                    "image_url": item.get("image") or item.get("thumbnail"),
                })
            return normalized

        # Which endpoint each host should use
        ENDPOINT_SELECTION = {
            "yahoo-finance166": "api/news/list",             # requires region + snippetCount
            "investing-com6": "web-crawling/api/news/latest", # no query params
            "yahoo-finance15": "api/v2/markets/news",        # requires tickers + type
            "yahoo-finance-api-data": "news/hot-news",       # requires limit only
          "yh-finance": "api/news/list",   
             
        }

        # Params builder for each host
        PARAMS_MAP = {
           "yahoo-finance166": lambda region, count, **kwargs: {
        "region": region,
        "snippetCount": count
    },
    "yh-finance": lambda region, count, **kwargs: {
        "region": region,
        "snippetCount": count
    },

    # ✅ Yahoo Finance 15 → needs tickers + type
    # we can fallback to "AAPL" if not provided
    "yahoo-finance15": lambda region, count, **kwargs: {
        "tickers": kwargs.get("tickers", "AAPL"),
        "type": kwargs.get("type", "ALL")
    },

    # ✅ Yahoo Finance API Data → needs only limit
    "yahoo-finance-api-data": lambda region, count, **kwargs: {
        "limit": count
    },

    # ✅ Investing.com → NO params required
    "investing-com6": lambda *args, **kwargs: None,
        }

        for base in BASE_URLs:
            try:
                host = base.split("//")[-1].split("/")[0]
                key = next((k for k in PARAMS_MAP if k in host), None)

                if not key:
                    errors.append(f"{base}: No matching key in PARAMS_MAP")
                    continue

                endpoint = ENDPOINT_SELECTION.get(key)
                if not endpoint:
                    errors.append(f"{base}: No endpoint mapping found")
                    continue

                url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
                params = PARAMS_MAP[key](region, snippet_count)

                headers = HEADERS[0]
                response = requests.get(url, headers=headers, params=params)
                print(f"[DEBUG] Trying {url} with params={params}")

                if response.status_code == 404:
                    print(f"[newslist] Skipping {url} (404 Not Found)")
                    continue


                response.raise_for_status()
                raw = response.json()
                print(f"[newslist] Raw response from {url}: {str(raw)[:200]}...")

                # Always attempt normalization, even if structure is unexpected
                articles = normalize_articles(raw)
                if not articles:
                    print(f"[newslist] {url} returned no articles after normalization, skipping…")
                    # Log the raw data for debugging
                    errors.append(f"{url}: No articles after normalization. Raw: {str(raw)[:200]}")
                    continue

                all_articles.extend(articles[:snippet_count])
                if len(all_articles) >= snippet_count:
                    break  # Got enough articles

            except Exception as e:
                errors.append(f"{base}: {str(e)}")
                print(f"[newslist] Error with {base}: {str(e)}")
                continue
            time.sleep(1)  # polite delay after each API call

        if not all_articles:
            return Response(
                {"status": "empty", "message": "No news found", "errors": errors},
                status=200
            )

        return Response({"status": "success", "articles": all_articles[:snippet_count]})

    except Exception as e:
        import traceback
        print("[newslist] Fatal error:")
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)

@api_view(["GET"])
def newsdetails(request):
    try:
        article_id = request.GET.get("article_id") or request.GET.get("uuid")
        region = request.GET.get("region", "US")
        errors = []

        if not article_id:
            print("[newsdetails] Error: Missing article_id in request")
            return Response({"status": "error", "message": "Missing article_id"}, status=400)

        # Endpoint and param mapping for each host
        ENDPOINT_SELECTION = {
            "yahoo-finance166": "api/news/details",
            "investing-com6": "web-crawling/api/news/details",
            "yahoo-finance15": "api/v2/markets/news/details",  # hypothetical, adjust as needed
            "yahoo-finance-api-data": "news/detail",
            "yh-finance": "api/news/details",
        }

        PARAMS_MAP = {
            "yahoo-finance166": lambda region, count, **kwargs: {"uuid": kwargs.get("article_id"), "region": region},
            "yh-finance": lambda region, count, **kwargs: {"uuid": kwargs.get("article_id"), "region": region},
            "yahoo-finance15": lambda region, count, **kwargs: {"uuid": kwargs.get("article_id"), "region": region},
            "yahoo-finance-api-data": lambda region, count, **kwargs: {"id": kwargs.get("article_id")},
            "investing-com6": lambda *args, **kwargs: {"id": kwargs.get("article_id")},
        }

        def normalize_article(raw):
            if not raw:
                return None
            # Try all possible keys for article detail
            if isinstance(raw, dict):
                for key in ("data", "item", "body", "article"):
                    if key in raw and isinstance(raw[key], (dict, list)):
                        return raw[key]
            return raw

        for base in BASE_URLs:
            try:
                host = base.split("//")[-1].split("/")[0]
                key = next((k for k in PARAMS_MAP if k in host), None)
                if not key:
                    errors.append(f"{base}: No matching key in PARAMS_MAP")
                    continue
                endpoint = ENDPOINT_SELECTION.get(key)
                if not endpoint:
                    errors.append(f"{base}: No endpoint mapping found")
                    continue
                url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
                params = PARAMS_MAP[key](region, 0, article_id=article_id)
                headers = HEADERS[0]
                response = requests.get(url, headers=headers, params=params)
                print(f"[DEBUG] Trying {url} with params={params}")

                if response.status_code == 404:
                    print(f"[newsdetails] Skipping {url} (404 Not Found)")
                    continue

                response.raise_for_status()
                raw = response.json()
                print(f"[newsdetails] Raw response from {url}: {str(raw)[:200]}...")

                article = normalize_article(raw)
                if not article:
                    print(f"[newsdetails] {url} returned no article data after normalization, skipping…")
                    errors.append(f"{url}: No article after normalization. Raw: {str(raw)[:200]}")
                    continue

                return Response({"status": "success", "article": article})

            except Exception as e:
                errors.append(f"{base}: {str(e)}")
                print(f"[newsdetails] Error with {base}: {str(e)}")
                continue
            time.sleep(1)  # polite delay after each API call

        # If no article found from any API, return JSON with status and errors
        print(f"[newsdetails] No article found. Errors: {errors}")
        return Response(
            {"status": "empty", "message": "No details found", "errors": errors},
            status=200
        )
    except Exception as e:
        import traceback
        print("[newsdetails] Fatal error:")
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)
    

@api_view(["GET"])
def ticker_history(request):
    """
    Fetch historical data for one or multiple symbols, looping over multiple APIs.
    """
    try:
        symbols_param = request.GET.get("symbol")
        interval = request.GET.get("interval", "1d")
        limit = int(request.GET.get("limit", 100))
        api_index = int(request.GET.get("api_index", 0))
        diffandsplits = request.GET.get("diffandsplits", "false")

        if symbols_param:
            symbols = [s.strip().upper() for s in symbols_param.split(",")]
        else:
            symbols = list(Ticker.objects.values_list("symbol", flat=True))
            if not symbols:
                return Response({
                    "status": "error",
                    "message": "No symbols available in database. Please load tickers first."
                }, status=404)

        results, skipped_calls = [], []

        # --- ENDPOINTS ---
        ENDPOINT_SELECTION = {
            "yahoo-finance15": [
                "api/v2/markets/stock/history",  # needs symbol + interval + limit
                "api/v1/markets/stock/history",  # needs symbol + interval + diffandsplits
            ]
        }

        PARAMS_MAP = {
            "api/v2/markets/stock/history": lambda s, i, l, **kwargs: {
                "symbol": s,
                "interval": i,
                "limit": l
            },
            "api/v1/markets/stock/history": lambda s, i, l, **kwargs: {
                "symbol": s,
                "interval": i,
                "diffandsplits": kwargs.get("diffandsplits", "false")
            },
        }

        def normalize_history(raw):
            """Ensure we always get a list of rows"""
            if not raw or not isinstance(raw, dict):
                return []
            if "body" in raw and isinstance(raw["body"], list):
                return raw["body"]
            if "items" in raw and isinstance(raw["items"], list):
                return raw["items"]
            if "body" in raw and isinstance(raw["body"], dict) and "items":
                return raw["body"]["items"]
            if "data" in raw and isinstance(raw["data"], list):
                return raw["data"]
            if isinstance(raw, dict) and "data" in raw:
                return raw["data"]
            print(f"[normalize_history] Unknown format, keys={list(raw.keys())}")
            return []

        # --- LOOP SYMBOLS ---

        for symbol in symbols[:10]:  # Limit to first 10 tickers
            inserted_any = 0
            for base in BASE_URLs:
                host = base.split("//")[-1].split("/")[0]
                key = next((k for k in ENDPOINT_SELECTION if k in host), None)

                if not key:
                    skipped_calls.append({"symbol": symbol, "reason": f"{base}: No matching key"})
                    continue

                endpoints = ENDPOINT_SELECTION.get(key, [])
                for endpoint in endpoints:
                    try:
                        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
                        params = PARAMS_MAP[endpoint](symbol, interval, limit, diffandsplits=diffandsplits)

                        headers = HEADERS[api_index % len(HEADERS)]
                        response = requests.get(url, headers=headers, params=params, timeout=15)
                        print(f"[DEBUG] Trying {url} with params={params}")

                        if response.status_code == 404:
                            print(f"[ticker_history] Skipping {url} (404 Not Found)")
                            continue

                        response.raise_for_status()
                        raw = response.json()
                        print(f"[ticker_history] Raw response from {url}: {str(raw)[:200]}...")

                        rows = normalize_history(raw)
                        if not rows:
                            print(f"[ticker_history] {url} returned no rows")
                            continue

                        inserted = save_ticker_history(symbol, interval, {"data": rows})
                        if inserted > 0:
                            inserted_any += inserted
                            results.append({
                                "symbol": symbol,
                                "interval": interval,
                                "rows_inserted": inserted,
                                "sample": rows[:3]
                            })
                            break  # ✅ success, don’t try other endpoints for this symbol

                    except Exception as e:
                        import traceback
                        skipped_calls.append({"symbol": symbol, "reason": f"{url}: {str(e)}"})
                        print(f"[ticker_history] Error with {url}: {str(e)}")
                        print(traceback.format_exc())
                        continue
                    time.sleep(1)  # polite delay

            if inserted_any == 0:
                # DB fallback: try to get up to 10 cached rows from TickerHistory
                cached = list(TickerHistory.objects.filter(symbol=symbol, interval=interval).order_by('-timestamp')[:10])
                if cached:
                    print(f"[ticker_history] DB fallback for {symbol}: returning {len(cached)} cached rows")
                    results.append({
                        "symbol": symbol,
                        "interval": interval,
                        "rows_inserted": 0,
                        "sample": [
                            {
                                "timestamp": row.timestamp,
                                "open": row.open_price,
                                "high": row.high_price,
                                "low": row.low_price,
                                "close": row.close_price,
                                "volume": row.volume
                            } for row in cached
                        ]
                    })
                else:
                    skipped_calls.append({"symbol": symbol, "reason": "No data inserted from any API and no cached data in DB"})
                    print(f"[ticker_history] Skipped {symbol}: No rows inserted from all endpoints and no DB fallback")

        return Response({"status": "success", "results": results, "skipped_calls": skipped_calls})

    except Exception as e:
        import traceback
        print("[ticker_history] Fatal error:")
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)
    
def normalize_history(raw):
    """
    Normalize Yahoo Finance API responses (v1, v2, etc.)
    Always return a list of OHLCV rows.
    """
    if not raw or not isinstance(raw, dict):
        return []

    # v2 format → { meta:..., body:[...] }
    if "body" in raw and isinstance(raw["body"], list):
        return raw["body"]

    # v1 format → { meta:..., items:[...] }
    if "items" in raw and isinstance(raw["items"], list):
        return raw["items"]

    # Some v1 responses → { body: { items:[...] } }
    if "body" in raw and isinstance(raw["body"], dict) and "items" in raw["body"]:
        return raw["body"]["items"]

    # Some fallback APIs use { data:[...] }
    if "data" in raw and isinstance(raw["data"], list):
        return raw["data"]

    print(f"[normalize_history] Unknown format, keys={list(raw.keys())}")
    return []
      
def save_ticker_history(symbol, interval, raw_data):
    """
    Save ticker history to DB, handling both v1/v2 formats.
    """
    try:
        rows = normalize_history(raw_data)
        if not rows:
            print(f"[save_ticker_history] No rows for {symbol}")
            return 0

        df = pd.DataFrame(rows)
        if df.empty:
            print(f"[save_ticker_history] Empty DataFrame for {symbol}")
            return 0

        normalized_rows = []
        for _, row in df.iterrows():
            try:
                # Handle timestamp/date fields
                ts = row.get("date") or row.get("datetime") or row.get("timestamp")
                if not ts:
                    print(f"[save_ticker_history] Missing timestamp for {symbol}, skipping row")
                    continue

                history = TickerHistory(
                    symbol=symbol,
                    interval=interval,
                    timestamp=pd.to_datetime(ts, errors="coerce"),
                    open_price=row.get("open") or row.get("o"),
                    high_price=row.get("high") or row.get("h"),
                    low_price=row.get("low") or row.get("l"),
                    close_price=row.get("close") or row.get("c"),
                    volume=row.get("volume") or row.get("v"),
                )
                normalized_rows.append(history)
            except Exception as e:
                print(f"[save_ticker_history] Skipping bad row for {symbol}: {e}")
                continue

        if normalized_rows:
            TickerHistory.objects.bulk_create(normalized_rows, ignore_conflicts=True)
            print(f"[save_ticker_history] Inserted {len(normalized_rows)} rows for {symbol}")
        else:
            print(f"[save_ticker_history] Nothing to insert for {symbol}")

        return len(normalized_rows)

    except Exception as e:
        import traceback
        print(f"[save_ticker_history] Fatal error while saving {symbol}: {e}")
        print(traceback.format_exc())
        return 0

