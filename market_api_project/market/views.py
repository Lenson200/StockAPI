from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests
from market.services.rapidapi import call_api
import time
from .models import Ticker
import pandas as pd

# Create your views here.
@api_view(["GET"])
def tickers(request):
    try:
        TYPES = ["STOCKS", "ETFS", "MUTUALFUNDS", "CURRENCIES", "CRYPTOCURRENCIES", "COMMODITIES"]
        max_api_index = int(request.GET.get("max_api_index", 10))  # default 10
        limit = int(request.GET.get("limit", 100))

        all_data = []
        for api_index in range(max_api_index):
            for t in TYPES:
                params = {"type": t, "limit": limit}

                data = call_api("api/v2/markets/tickers", params=params, api_index=api_index)
                if not data:
                    continue  # skip empty responses

                if isinstance(data, dict) and "data" in data:
                    data = data["data"]  # many APIs wrap results

                if not isinstance(data, list):
                    # log or raise error instead of crashing
                    print(f"Unexpected response for {t} @ index {api_index}: {data}")
                    continue

                for row in data:
                    row["market"] = t
                all_data.extend(data)

                time.sleep(2)  # Delay between each API call

        if not all_data:
            return Response({"status": "error", "message": "No valid data fetched"}, status=502)

        df = pd.DataFrame(all_data)
        print(df.head())

        tickers = [
            Ticker(symbol=row["symbol"], price=row["price"], market=row["market"])
            for _, row in df.iterrows()
        ]
        Ticker.objects.bulk_create(tickers, ignore_conflicts=True)

        return Response({
            "status": "success",
            "inserted_rows": len(tickers),
            "sample": df.head().to_dict(orient="records"),
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)


# @api_view(["GET"])
# def tickers(request):
#     try:
#         TYPES = ["STOCKS", "ETFS", "MUTUALFUNDS", "CURRENCIES", "CRYPTOCURRENCIES", "COMMODITIES"]
#         max_api_index = int(request.GET.get("max_api_index", 10))  # default to 10
#         limit = int(request.GET.get("limit", 100))

#         all_data = []
#         for api_index in range(max_api_index):
#             for t in TYPES:
#                 params = {"type": t}
#                 data = call_api("api/v2/markets/tickers", params=params, api_index=api_index)
#                 if isinstance(data, list):
#                     for row in data:
#                         row["market"] = t
#                     all_data.extend(data)
#                 time.sleep(2)  # Delay between each API call

#         df = pd.DataFrame(all_data)
#         print(df.head())
#         tickers = [
#             Ticker(symbol=row["symbol"], price=row["price"], market=row["market"])
#             for _, row in df.iterrows()
#         ]
#         Ticker.objects.bulk_create(tickers, ignore_conflicts=True)

#         return Response({
#             "status": "success",
#             "inserted_rows": len(tickers),
#             "sample": df.head().to_dict(orient="records"),
#         })
#     except Exception as e:
#         import traceback
#         print(traceback.format_exc())
#         return Response({"status": "error", "message": str(e)}, status=500)

#     print("Status code:", response.status_code)
#     print("Response text:", response.text)
