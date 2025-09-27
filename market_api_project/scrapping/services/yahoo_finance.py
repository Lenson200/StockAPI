import requests
from bs4 import BeautifulSoup
from django.http import JsonResponse
import yfinance as yf
import datetime
from datetime import timedelta
import requests
from bs4 import BeautifulSoup

import time, requests

def get_yahoo_screener(scr_id="most_actives", count=100, start=0):
    url = (
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        f"?formatted=true&scrIds={scr_id}&start={start}&count={count}"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return {"error": f"Failed to fetch data: {response.status_code}"}

    data = response.json()

    try:
        quotes = data["finance"]["result"][0]["quotes"]
        result = []
        for q in quotes:
            result.append({
                "symbol": q.get("symbol"),
                "shortName": q.get("shortName"),
                "regularMarketPrice": q.get("regularMarketPrice", {}).get("raw"),
                "regularMarketChangePercent": q.get("regularMarketChangePercent", {}).get("raw"),
                "regularMarketVolume": q.get("regularMarketVolume", {}).get("raw"),
                "marketCap": q.get("marketCap", {}).get("raw"),
            })
        return result
    except Exception as e:
        return {"error": str(e)}
    
def get_yahoo_ohlcv(symbol, interval="1d", range_="5d", retries=3, delay=3):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": interval, "range": range_}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://finance.yahoo.com/quote/{symbol}/history"
    }

    for attempt in range(1, retries+1):
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            indicators = result["indicators"]["quote"][0]

            ohlcv = []
            for i, ts in enumerate(timestamps):
                ohlcv.append({
                    "timestamp": ts,
                    "open": indicators["open"][i],
                    "high": indicators["high"][i],
                    "low": indicators["low"][i],
                    "close": indicators["close"][i],
                    "volume": indicators["volume"][i]
                })
            return ohlcv

        print(f"[WARN] Attempt {attempt} failed: {response.text}")
        time.sleep(delay * attempt)  # exponential backoff

    raise Exception(f"Yahoo Finance blocked requests after {retries} retries.")


def get_yahoo_history(symbol):
    url = f"https://finance.yahoo.com/quote/{symbol}/history?p={symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",}
    response = requests.get(url, headers=headers)

    print(f"[DEBUG] Requesting URL: {url}")
    print(f"[DEBUG] Status code: {response.status_code}")

    if response.status_code != 200:
        return {"error": "Failed to fetch data"}
    
    soup = BeautifulSoup(response.text, 'html.parser')

    container = soup.find("div", {"data-testid": "history-table"})
    print(f"[DEBUG] Container found: {bool(container)}")

    if not container:
        return {"error": "History table not found"}
    
    table = container.find("table")
    print(f"[DEBUG] Table found: {bool(table)}")

    if not table:
        return {"error": "No table found in container"}
    
    rows = table.find_all('tr')
    print(f"[DEBUG] Number of rows found (including header): {len(rows)}")

    history = []
    for i, row in enumerate(rows[1:], start=1):  # Skip header row
        cols = [col.text.strip() for col in row.find_all("td")]
        print(f"[DEBUG] Row {i} columns: {cols}")

        if len(cols) < 7:
            continue
        try:
            history.append({
                "date": cols[0],
                "open": float(cols[1].replace(',', '')) if cols[1] != 'N/A' else None,
                "high": float(cols[2].replace(',', '')) if cols[2] != 'N/A' else None,
                "low": float(cols[3].replace(',', '')) if cols[3] != 'N/A' else None,
                "close": float(cols[4].replace(',', '')) if cols[4] != 'N/A' else None,
                "adj_close": float(cols[5].replace(',', '')) if cols[5] != 'N/A' else None,
                "volume": int(cols[6].replace(',', '').replace('-', '0')) if cols[6] != 'N/A' else None,
            })
        except ValueError as e:
            print(f"[DEBUG] ValueError on row {i}: {e}")
            continue
    
    print(f"[DEBUG] Parsed {len(history)} rows successfully")
    return {"symbol": symbol, "history": history}
