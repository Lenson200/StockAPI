from django.urls import path
from market.views import tickers,ticker_history,newslist,newsdetails,charts

urlpatterns = [

     path('tickers/', tickers, name='tickers'),
     path("history/", ticker_history, name="ticker_history"),
     path("newslist/", newslist, name="newslist"),
     path("newsdetails/", newsdetails, name="newsdetails"),
     path("charts/", charts, name="charts"),
     ]

