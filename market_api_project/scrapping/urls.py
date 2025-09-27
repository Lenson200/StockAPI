
from django.urls import path
from .views import yahoo_history,ohlcv_view,most_active,top_gainers,top_losers,most_active_tv

urlpatterns = [
    path("yahoo/most-active/", most_active, name="yahoo-most-active"),
    path("yahoo/history/", yahoo_history, name="yahoo-history"),
    path("yahoo/top-gainers/", top_gainers, name="yahoo-top-gainers"),
    path("yahoo/top-losers/", top_losers, name="yahoo-top-losers"),
    path("ohlcv/<str:symbol>/", ohlcv_view, name="ohlcv"),
    path("tradingview/most-active/", most_active_tv, name="tv-most-active"),

     ]

