# StockAPI

A Django-based API for fetching and scrapping stock market data from Yahoo Finance, TradingView, and other providers. This project supports both direct API calls (via RapidAPI) and web scraping endpoints.

## Features
- Fetch most active, top gainers, and top losers from Yahoo Finance and TradingView
- Retrieve ticker lists, historical data, news, and chart data via RapidAPI
- Database caching for historical data
- Modular service structure for easy extension

## Applications
This project is divided into two Django apps:

1. **Scrapping App**:
   - Handles scraping and reverse-engineering of data from Yahoo Finance and TradingView.
   - Endpoints:
     - `/scrapapi/yahoo/most-active/?count=10&start=0`
     - `/scrapapi/yahoo/top-gainers/?count=10&start=0`
     - `/scrapapi/yahoo/top-losers/?count=10&start=0`
     - `/scrapapi/tradingview/most-active/?region=india&count=10&start=0`

   Example:
   ```
   GET http://localhost:8000/scrapapi/yahoo/most-active/?count=10&start=0
   ```

2. **Market App**:
   - Integrates official/paid APIs as fallbacks for reliable data retrieval.
   - Endpoints:
     - `/api/tickers/?max_api_index=2&limit=10`
     - `/api/history/?symbol=AAPL&interval=1m&limit=10`
     - `/api/newslist`
     - `/api/charts/?symbol=aapl&period=1Y`

   Example:
   ```
   GET http://localhost:8000/api/tickers/?max_api_index=2&limit=10
   ```

## Scrapping Endpoints (No API Key Required)
If running locally use this to test the APIs'http//:localhost:8000'.

- `/scrapapi/yahoo/most-active/?count=10&start=0`
- `/scrapapi/yahoo/top-gainers/?count=10&start=0`
- `/scrapapi/yahoo/top-losers/?count=10&start=0`
- `/scrapapi/tradingview/most-active/?region=india&count=10&start=0`

Example:
```
GET http://localhost:8000/scrapapi/yahoo/most-active/?count=10&start=0
```

## API Endpoints (RapidAPI Key Required)
You must create a RapidAPI account and set up your `.env` file as described below.

- `/api/tickers/?max_api_index=2&limit=10`
- `/api/history/?symbol=AAPL&interval=1m&limit=10`
- `/api/newslist`
- `/api/charts/?symbol=aapl&period=1Y`

Example:
```
GET http://localhost:8000/api/tickers/?max_api_index=2&limit=10
```

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd StockAPI
   ```

2. **Create a `.env` file in the project root:**
   - Go to [RapidAPI](https://rapidapi.com/), create an account, and copy your API key.
   - Add the following to your `.env` file:
     ```
     RAPIDAPI_KEY=your-client-key-here
     RAPIDAPI_HOST=example-rapidapi-provider.p.rapidapi.com
     ```

3. **Install dependencies and run the server:**
   ```bash
   # (Optional) Create and activate a virtual environment
   python3 -m venv env
   source env/bin/activate
   pip install -r requirements.txt

   # Run migrations
   python manage.py migrate

   # Start the server
   python manage.py runserver
   ```

4. **Test in Postman or your browser:**
   - Example:
     ```
     GET http://localhost:8000/api/market/tickers/
     ```
## Important Notes on Scraping vs Official APIs

This project provides two ways of getting stock market data:

### Scraping App (Free, but Limited)
- **How it works:** Extracts data directly from Yahoo Finance and TradingView websites.
- **Pros:** No API key or subscription needed.
- **Cons / Limitations:**
  - Fragile: If Yahoo/TradingView update their site, scraping will break without warning.
  - Unreliable: No guarantee of complete or timely data.
  - Block Risk: Providers may block scrapers, causing sudden downtime.
  - Maintenance Heavy: Frequent fixes may be required to keep it working.

**Bottom line:** Scraping is fine for testing, demos, or proof-of-concept, but it is not recommended for production use.

### Market App (RapidAPI Endpoints)
- **How it works:** Uses official APIs via RapidAPI.
- **Pros:** More reliable, scalable, and supported. Can upgrade to higher tiers if needed.
- **Cons:** Requires a free RapidAPI account and key. Free tier has request limits.

**Recommendation:**  
For long-term stability and business use, prefer the Market App (RapidAPI). Use the Scraping App only as a fallback or for lightweight testing.

## Notes
- For all `/api/` endpoints, a valid RapidAPI key is required in your `.env` file.
- For `/scrapapi/` endpoints, no API key is required.
- Use `localhost:8000` if running locally and any other url link to your workspace if you are on codespaces..

---

For questions or issues, please open an issue in this repository.
