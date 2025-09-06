# common/providers/fred_provider.py
import requests, pandas as pd
from common.config.settings import SETTINGS
from common.cache.cache import get_cache
from common.providers.base import DataProvider

class FredProvider(DataProvider):
    def get_macro_series(self, series_id: str) -> pd.DataFrame:
        if not SETTINGS.fred_key:
            return pd.DataFrame()

        cache = get_cache()
        key = f"fred:{series_id}"

        # 1) tenta cache
        cached = cache.get(key)
        if cached:
            # cached é um dict serializável: {"date": [...], "value": [...]}
            df = pd.DataFrame(cached)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            if "value" in df.columns:
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df

        # 2) baixa da API
        url = "https://api.stlouisfed.org/fred/series/observations"
        r = requests.get(
            url,
            params={"series_id": series_id, "api_key": SETTINGS.fred_key, "file_type": "json"},
            timeout=15
        )
        if r.status_code != 200:
            return pd.DataFrame()

        obs = r.json().get("observations", [])
        if not obs:
            return pd.DataFrame()

        df = pd.DataFrame(obs)[["date", "value"]]
        # normaliza tipos
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        # 3) salva no cache com tipos serializáveis (date -> string ISO)
        serializable = {
            "date": df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "value": df["value"].where(df["value"].notna(), None).tolist(),
        }
        cache.set(key, serializable, SETTINGS.ttl_macro)
        return df
