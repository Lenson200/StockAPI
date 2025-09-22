from django.urls import path
from market.views import tickers,ticker_history

urlpatterns = [

     path('tickers/', tickers, name='tickers'),
     path("market/history/", ticker_history, name="ticker_history"),]

