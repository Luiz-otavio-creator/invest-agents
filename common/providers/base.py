# common/providers/base.py
from typing import Dict
import pandas as pd

class DataProvider:
    def get_price(self, symbol: str): return None
    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame: 
        return pd.DataFrame()
    def get_fundamentals(self, symbol: str) -> Dict: 
        return {}
    def get_macro_series(self, series_id: str) -> pd.DataFrame: 
        return pd.DataFrame()
