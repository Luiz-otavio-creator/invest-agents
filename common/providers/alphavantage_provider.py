# common/providers/alphavantage_provider.py
import requests
from typing import Dict
from common.config.settings import SETTINGS
from common.cache.cache import get_cache
from common.providers.base import DataProvider

BASE = "https://www.alphavantage.co/query"

class AlphaVantageProvider(DataProvider):
    def get_fundamentals(self, symbol: str) -> Dict:
        if not SETTINGS.alphavantage_key:
            return {}
        key = f"av:overview:{symbol.upper()}"
        cache = get_cache()
        if (v := cache.get(key)) is not None:
            return v
        r = requests.get(BASE, params={
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": SETTINGS.alphavantage_key
        }, timeout=15)
        if r.status_code != 200:
            return {}
        data = r.json() or {}

        # Helpers
        def safe_div(a, b):
            try:
                return float(a) / float(b) if a is not None and b not in (0, None) else None
            except Exception:
                return None

        # Normaliza campos úteis para score/relatório
        out = {
            "name": data.get("Name"),
            "pe": _to_float(data.get("PERatio")),
            "roe": _to_float(data.get("ReturnOnEquityTTM")),
            "profit_margin": _to_float(data.get("ProfitMargin")),
            "operating_margin": _to_float(data.get("OperatingMarginTTM")),
            "revenue_ttm": _to_float(data.get("RevenueTTM")),
        }

        # 🔥 Novos indicadores
        total_debt = _to_float(data.get("TotalDebt"))
        ebitda = _to_float(data.get("EBITDA"))
        out["debt_ebitda"] = safe_div(total_debt, ebitda)

        revenue_ttm = _to_float(data.get("RevenueTTM"))
        revenue_prev = _to_float(data.get("QuarterlyRevenueGrowthYOY"))  # proxy
        if revenue_ttm is not None and revenue_prev is not None:
            out["rev_growth"] = safe_div(revenue_ttm - revenue_prev, revenue_prev)
        else:
            out["rev_growth"] = None

        eps_ttm = _to_float(data.get("EPS"))
        eps_prev = _to_float(data.get("DilutedEPSTTM"))  # pode ajustar se houver campo mais estável
        out["eps_growth"] = safe_div((eps_ttm or 0) - (eps_prev or 0), eps_prev)

        cache.set(key, out, SETTINGS.ttl_fundamentals)
        return out

def _to_float(x, default=None):
    try:
        return float(x)
    except:
        return default
