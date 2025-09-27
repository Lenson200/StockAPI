import requests
import time

def get_tradingview_screener(region="america", limit=20, start=0):
    url = f"https://scanner.tradingview.com/{region}/scan"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    columns = [
        "logoid", "symbol", "name", "price", 
        "volume", "marketCap", "changePercent", "changeAbs"
    ]

    payload = {
        "filter": [],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "logoid", "name", "close", "volume", 
            "market_cap_basic", "change", "change_abs"
        ],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [start, start + limit]
    }

    time.sleep(1)  

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        return {"error": f"Failed with {response.status_code}"}

    try:
        data = response.json()
        result = []
        for d in data.get("data", []):
            values = d.get("d", [])
            mapped = dict(zip(columns, values))
            result.append(mapped)
        return result
    
    except Exception as e:
        return {"error": str(e)}
