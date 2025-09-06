# test_apis.py
import os, requests
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

alpha_key = os.getenv("ALPHAVANTAGE_API_KEY")
fred_key  = os.getenv("FRED_API_KEY")

# ---------- AlphaVantage: OVERVIEW da AAPL ----------
alpha_url = "https://www.alphavantage.co/query"
r1 = requests.get(alpha_url, params={
    "function": "OVERVIEW",
    "symbol": "AAPL",
    "apikey": alpha_key
}, timeout=15)

print("AlphaVantage status:", r1.status_code)
data1 = r1.json()
print("Alpha sample fields:",
      {k: data1.get(k) for k in ("Name","PERatio","ProfitMargin","ReturnOnEquityTTM")})

# ---------- FRED: série DGS10 (10y Treasury) ----------
fred_url = "https://api.stlouisfed.org/fred/series/observations"
r2 = requests.get(fred_url, params={
    "series_id": "DGS10",
    "api_key": fred_key,
    "file_type": "json"
}, timeout=15)

print("FRED status:", r2.status_code)
data2 = r2.json()
print("FRED points:", len(data2.get("observations", [])))
