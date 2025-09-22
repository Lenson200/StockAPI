from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests
from market.services.rapidapi import call_api
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


def fetch_ticker_history(symbol: str, interval: str = "1d", limit: int = 100, api_index: int = 0):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    return call_api("api/v2/markets/stock/history", params=params, api_index=api_index)

@api_view(["GET"])
def ticker_history(request):
    """
    Example:
    GET /api/market/history/?symbol=AAPL,MSFT&interval=1d&limit=100
    If no `symbol` provided, fallback = symbols from Ticker DB.
    """
    try:
        symbols_param = request.GET.get("symbol")
        interval = request.GET.get("interval", "1d")
        limit = int(request.GET.get("limit", 100))
        api_index = int(request.GET.get("api_index", 0))

        if symbols_param:
            # Case 1: user gave ?symbol=AAPL,MSFT
            symbols = [s.strip().upper() for s in symbols_param.split(",")]
        else:
            # Case 2: pull all symbols from Ticker model
            symbols = list(Ticker.objects.values_list("symbol", flat=True))

            if not symbols:
                return Response({
                    "status": "error",
                    "message": "No symbols available in database. Please load tickers first."
                }, status=404)

        results = []
        for symbol in symbols:
            raw = fetch_ticker_history(symbol, interval=interval, limit=limit, api_index=api_index)
            inserted = save_ticker_history(symbol, interval, raw)

            results.append({
                "symbol": symbol,
                "interval": interval,
                "rows_inserted": inserted,
                "sample": raw.get("data", [])[:3]  # preview first 3 rows
            })

        return Response({"status": "success", "results": results})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)
        
def save_ticker_history(symbol, interval, raw_data):
    if not raw_data or "data" not in raw_data:
        return 0

    df = pd.DataFrame(raw_data["data"])
    if df.empty:
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
            print(f"Skipping row for {symbol}: {e}")
            continue

    if normalized_rows:
        TickerHistory.objects.bulk_create(normalized_rows, ignore_conflicts=True)
    return len(normalized_rows)
