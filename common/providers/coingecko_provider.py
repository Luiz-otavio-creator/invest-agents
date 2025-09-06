# common/providers/coingecko_provider.py
import requests, pandas as pd
from typing import Optional
from common.cache.cache import get_cache
from common.config.settings import SETTINGS
from common.providers.base import DataProvider

CG_IDS = {"BTC":"bitcoin","ETH":"ethereum","SOL":"solana","ADA":"cardano","DOGE":"dogecoin"}

class CoinGeckoProvider(DataProvider):
    def get_price(self, symbol: str) -> Optional[float]:
        sid = CG_IDS.get(symbol.upper())
        if not sid: return None
        key = f"cg:price:{sid}"
        cache = get_cache()
        if (v := cache.get(key)) is not None: 
            return float(v)
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": sid, "vs_currencies":"usd"}, timeout=15)
        if r.status_code != 200: 
            return None
        p = r.json().get(sid, {}).get("usd")
        if p is not None:
            cache.set(key, float(p), SETTINGS.ttl_price)
            return float(p)
        return None

    # histórico opcional (não obrigatório pro MVP)
