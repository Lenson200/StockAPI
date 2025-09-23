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
        region= request.GET.get("region", "US")
        snippet_count= int(request.GET.get("snippetCount", 10))

        ENDPOINTS= {
            "newslist": "api/news/list",
            "market_news": "/v2/market/news",
            "most_popular": "/web-crawling/api/news/most-popular"
            }

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
        for base in BASE_URLs:
            try:
                url = f"{base.rstrip('/')}/{ENDPOINTS['most_popular'].lstrip('/')}"
                headers = HEADERS[0]  # rotate if needed
                params = {"region": region, "snippetCount": snippet_count}
                response = requests.get(url, headers=headers, params=params)

                print(f"[DEBUG] Trying {url} with params={params}")
                if response.status_code == 404:
                    print(f"[newslist] Skipping {url} (404 Not Found)")
                    continue

                response.raise_for_status()
                raw = response.json()
                print(f"[newslist] Raw response from {url}: {str(raw)[:200]}...")

                articles = normalize_articles(raw)
                if not articles:
                    print(f"[newslist] {url} returned no articles after normalization, skipping…")
                    continue

                all_articles.extend(articles[:snippet_count])
                if len(all_articles) >= snippet_count:
                    break  # Got enough articles

            except Exception as e:
                errors.append(f"{base}: {str(e)}")
                print(f"[newslist] Error with {base}: {str(e)}")
                continue
        if not all_articles:
            return Response(
                {"status": "empty", "message": "No news found", "errors": errors},
                status=204
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
        article_id = request.GET.get("article_id")
        ENDPOINTS= {
            "newsdetails": "/api/news/details"
            }

        if not article_id:
            return Response({"status": "error", "message": "Missing article_id"}, status=400)

        errors = []

        for base in BASE_URLs:
            try:
                url = f"{base}{ENDPOINTS['newsdetails']}"
                headers = HEADERS[0]
                params = {"uuid": article_id,
                            "region": "US",  # default region   
                          }
                response = requests.get(url, headers=headers, params=params)

                if response.status_code == 404:
                    continue

                response.raise_for_status()
                raw = response.json()
                print(f"[newsdetails] Raw response from {url}: {str(raw)[:200]}...")

                if not raw or "data" not in raw:
                    print(f"[newsdetails] {url} returned no 'data', skipping…")
                    continue

                return Response({"status": "success", "article": raw.get("data")})

            except Exception as e:
                errors.append(f"{base}: {str(e)}")
                print(f"[newsdetails] Error with {base}: {str(e)}")
                continue

        return Response(
            {"status": "error", "message": "No details found", "errors": errors},
            status=404
        )
    except Exception as e:
        import traceback
        print("[newsdetails] Fatal error:")
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)
    



# @api_view(["GET"])
# def newslist(request):
#     region = request.GET.get("region", "US")
#     snippet_count = int(request.GET.get("snippetCount", 10))
    # ENDPOINTS= {
    #     "newslist": "/api/news/list"}
#     params = {"region": region, "snippetCount": snippet_count}
#     errors = []

#     for base in BASE_URLs:
#         try:
#             url = f"{base}{ENDPOINTS['newslist']}"
#             headers = HEADERS[0]  # rotate if needed
#             response = requests.get(url, headers=headers, params=params)

#             if response.status_code == 404:
#                 print(f"[newslist] Skipping {url} (404 Not Found)")
#                 continue

#             response.raise_for_status()
#             raw = response.json()

#             # On RapidAPI the news list usually comes in `data` or `items`
#             articles = raw.get("data") or raw.get("items") or raw
#             if not articles:
#                 print(f"[newslist] {url} returned empty data, skipping…")
#                 continue

#             return Response({"status": "success", "articles": articles[:snippet_count]})

#         except Exception as e:
#             errors.append(f"{base}: {str(e)}")
#             continue

#     return Response(
#         {"status": "empty", "message": "No news found", "errors": errors},
#         status=204
#     )

# @api_view(["GET"])
# def newsdetails(request):
#     article_id = request.GET.get("article_id")
#     ENDPOINTS= {
#         "newsdetails": "/api/news/details"}
    
#     if not article_id:
#         return Response({"status": "error", "message": "Missing article_id"}, status=400)

#     params = {"article_id": article_id}
#     errors = []

#     for base in BASE_URLs:
#         try:
#             url = f"{base}{ENDPOINTS['newsdetails']}"
#             headers = HEADERS[0]
#             response = requests.get(url, headers=headers, params=params)

#             if response.status_code == 404:
#                 continue

#             response.raise_for_status()
#             raw = response.json()

#             if not raw or "data" not in raw:
#                 continue

#             return Response({"status": "success", "article": raw.get("data")})

#         except Exception as e:
#             errors.append(f"{base}: {str(e)}")

#     return Response(
#         {"status": "error", "message": "No details found", "errors": errors},
#         status=404
#     )

def fetch_ticker_history(symbol: str, interval: str = "1m", limit: int = 10, api_index: int = 0):
    # Define possible endpoints and any parameter transformations
    endpoints = [
        {
            "url": "api/v2/markets/stock/history",
            "params": lambda s, i, l: {"symbol": s, "interval": i, "limit": l}
        },
        {
            "url": "api/v1/stock/historical-data",
            "params": lambda s, i, l: {"ticker": s, "timeframe": i, "count": l}
        }
    ]

    for ep in endpoints:
        url = ep["url"]
        params = ep["params"](symbol, interval, limit)

        try:
            raw = call_api(url, params=params, api_index=api_index)
            print(f"[fetch_ticker_history] Raw response from {url} for {symbol} @ interval={interval}, limit={limit}, api_index={api_index}: {str(raw)[:200]}...")

            # Normalize response
            if not raw:
                continue

            if isinstance(raw, dict):
                if raw.get("success") is False:
                    continue  # API-level failure, try next

                if "meta" in raw and "data" not in raw:
                    continue  # Meta-only response

                if "data" in raw:
                    return raw  # ✅ Success

        except Exception as e:
            print(f"[fetch_ticker_history] Error calling {url} for {symbol}: {e}")
            print(traceback.format_exc())
            continue  # Try next endpoint

    # If none succeed
    return {"data": [], "error": "All endpoints failed or returned invalid data"}
      
@api_view(["GET"])
def ticker_history(request):
    """
    Fetch historical data for one or multiple symbols.
    """
    try:
        symbols_param = request.GET.get("symbol")
        interval = request.GET.get("interval", "1d")
        limit = int(request.GET.get("limit", 100))
        api_index = int(request.GET.get("api_index", 0))

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

        for symbol in symbols:
            try:
                raw = fetch_ticker_history(symbol, interval=interval, limit=limit, api_index=api_index)

                if not raw or not raw.get("data"):
                    skipped_calls.append({"symbol": symbol, "reason": "No data returned from API"})
                    print(f"[ticker_history] Skipped {symbol}: No data")
                    continue

                inserted = save_ticker_history(symbol, interval, raw)

                if inserted == 0:
                    skipped_calls.append({"symbol": symbol, "reason": "Data returned but nothing inserted"})
                    print(f"[ticker_history] Skipped {symbol}: Data but no rows inserted")
                    continue

                results.append({
                    "symbol": symbol,
                    "interval": interval,
                    "rows_inserted": inserted,
                    "sample": raw.get("data", [])[:3]
                })
                print(f"[ticker_history] Inserted {inserted} rows for {symbol}")

            except Exception as e:
                import traceback
                err_msg = str(e)
                skipped_calls.append({"symbol": symbol, "reason": err_msg})
                print(f"[ticker_history] Error for {symbol}: {err_msg}")
                print(traceback.format_exc())
                continue
            time.sleep(2)  # polite delay

        return Response({"status": "success", "results": results, "skipped_calls": skipped_calls})

    except Exception as e:
        import traceback
        print("[ticker_history] Fatal error:")
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)
    
        
def save_ticker_history(symbol, interval, raw_data):
    """
    Save ticker history to DB, with debugging.
    """
    try:
        if not raw_data or "data" not in raw_data:
            print(f"[save_ticker_history] No 'data' for {symbol}")
            return 0

        df = pd.DataFrame(raw_data["data"])
        if df.empty:
            print(f"[save_ticker_history] Empty DataFrame for {symbol}")
            return 0

        normalized_rows = []
        for _, row in df.iterrows():
            try:
                history = TickerHistory(
                    symbol=symbol,
                    interval=interval,
                    timestamp=pd.to_datetime(row.get("date")),
                    open_price=row.get("open"),
                    high_price=row.get("high"),
                    low_price=row.get("low"),
                    close_price=row.get("close"),
                    volume=row.get("volume"),
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