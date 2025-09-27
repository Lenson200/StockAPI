from django.shortcuts import render
from scrapping.services.yahoo_finance import get_yahoo_history,get_yahoo_ohlcv,get_yahoo_screener
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse


# Create your views here.
@api_view(["GET"])
def most_active(request):
    count = int(request.GET.get("count", 100))
    start = int(request.GET.get("start", 0))
    data = get_yahoo_screener(scr_id="most_actives", count=count, start=start)

    return Response({
        "args": request.query_params,      # query parameters
        "headers": dict(request.headers),  # request headers
        "url": request.build_absolute_uri(), # full request URL
        "data": data                       # actual stock data
    })

@api_view(["GET"])
def top_gainers(request):
    count = int(request.GET.get("count", 100))
    start = int(request.GET.get("start", 0))
    data = get_yahoo_screener(scr_id="day_gainers", count=count, start=start)

    return Response({
        "args": request.query_params,
        "headers": dict(request.headers),
        "url": request.build_absolute_uri(),
        "data": data
    })
@api_view(["GET"])
def top_losers(request):
    count = int(request.GET.get("count", 100))
    start = int(request.GET.get("start", 0))
    data = get_yahoo_screener(scr_id="day_losers", count=count, start=start)

    return Response({
        "args": request.query_params,
        "headers": dict(request.headers),
        "url": request.build_absolute_uri(),
        "data": data
    })

@api_view(["GET"])
def ohlcv_view(request, symbol):
    interval = request.GET.get("interval", "1d")
    range_ = request.GET.get("range", "1mo")
    try:
        data = get_yahoo_ohlcv(symbol, interval=interval, range_=range_)
        return JsonResponse({"symbol": symbol, "ohlcv": data})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(["GET"])
def yahoo_history(request):
    symbol = request.GET.get("symbol", "AAPL")
    data = get_yahoo_history(symbol)
    return Response(data)