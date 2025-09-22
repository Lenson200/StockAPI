from django.urls import path
from market.views import tickers

urlpatterns = [

     path('tickers/', tickers, name='tickers'),]

