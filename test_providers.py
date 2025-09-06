# test_providers.py
from common.providers import latest_price, fundamentals, macro_series

print("AAPL price:", latest_price("AAPL"))
print("BTC price:", latest_price("BTC"))

f = fundamentals("AAPL")
print("AAPL fundamentals (subset):", {k: f.get(k) for k in ("pe","roe","profit_margin")})

df = macro_series("DGS10")
print("FRED DGS10 points:", len(df))
print(df.tail(3))
