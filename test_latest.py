# test_latest.py
from common.providers import latest_price, batch_latest_price, fundamentals, macro_series

print("AAPL:", latest_price("AAPL"))
print("BTC :", latest_price("BTC"))

print(batch_latest_price(["AAPL","MSFT","BTC","ETH","IPRP","IEAC"]))

print("Fundamentals AAPL:", fundamentals("AAPL"))
df = macro_series("DGS10")
print("FRED DGS10 rows:", None if df is None else len(df))
