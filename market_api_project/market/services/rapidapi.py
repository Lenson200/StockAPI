import requests
from django.conf import settings
from decouple import config

RAPIDAPI_KEY_1 = config('RAPIDAPI_KEY_1')
RAPIDAPI_KEY_2 = config('RAPIDAPI_KEY_2')
RAPIDAPI_KEY_3 = config('RAPIDAPI_KEY_3')
RAPIDAPI_KEY_4 = config('RAPIDAPI_KEY_4')

RAPIDAPI_HOST_1 = config("RAPIDAPI_HOST_1")
RAPIDAPI_HOST_2 = config("RAPIDAPI_HOST_2")
RAPIDAPI_HOST_3 = config("RAPIDAPI_HOST_3")
RAPIDAPI_HOST_4 = config("RAPIDAPI_HOST_4")


BASE_URLs = [
    "https://yahoo-finance15.p.rapidapi.com",
    "https://yh-finance.p.rapidapi.com",
    "https://yahoo-finance166.p.rapidapi.com",
    "https://investing-com6.p.rapidapi.com/web-crawling",
    "https://yahoo-finance-api-data.p.rapidapi.com",
    "https://seeking-alpha.p.rapidapi.com",
     "https://investing-real-time.p.rapidapi.com", 

]

HEADERS = [
    {
        "x-rapidapi-key": settings.RAPIDAPI_KEY_1,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_1,
    },
    {
       "x-rapidapi-key": settings.RAPIDAPI_KEY_2,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_2,
    },
    {
       "x-rapidapi-key": settings.RAPIDAPI_KEY_3,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_3,
    }
    ,
    {
       "x-rapidapi-key": settings.RAPIDAPI_KEY_4,
        "x-rapidapi-host": settings.RAPIDAPI_HOST_4,
    }
    
]

def call_api(endpoint: str, params=None, api_index=0):
    url = f"{BASE_URLs[api_index]}/{endpoint}"
    headers = HEADERS[api_index]
    response = requests.get(url, headers=headers, params=params or {})
    response.raise_for_status()
    return response.json()