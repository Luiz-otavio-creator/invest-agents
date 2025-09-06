# common/providers/yahoo_provider.py
# -----------------------------------------------------------------------------
# Provider do Yahoo Finance (yfinance) com:
# - Mapeamento de tickers EU/UK → sufixos corretos (.PA, .DE, .AS, .L, .MI, ...)
# - Extração segura de preços sem FutureWarning (usa .item() para escalares)
# - Tolerância a falhas (try/except) e retornos None elegantes
# - API simples: get_price(symbol) e get_history(symbol, period, interval)
# -----------------------------------------------------------------------------

from typing import Optional, Dict
import pandas as pd
import yfinance as yf

from common.providers.base import DataProvider

# -------------------------- MAPEAMENTO DE SÍMBOLOS ---------------------------
# Adicione aqui os tickers que precisam de sufixo no Yahoo.
YF_SYMBOL_MAP: Dict[str, str] = {
    # Europa blue chips
    "LVMH": "MC.PA",     # LVMH - Paris
    "ASML": "ASML.AS",   # ASML - Amsterdam
    "SAP":  "SAP.DE",    # SAP  - XETRA

    # ETFs/UCITS listados na Europa
    "IPRP": "IPRP.L",    # iShares Developed Property UCITS (LSE)
    "IEAC": "IEAC.MI",   # iShares Euro Corp Bond (Borsa Italiana)
    "IEGA": "IEGA.L",    # iShares Euro Govt Bond (LSE)

    # (US normalmente não precisa sufixo; deixe como está)
    # "AAPL": "AAPL", "MSFT": "MSFT", ...
}

def resolve_symbol(symbol: str) -> str:
    """Traduz o ticker 'lógico' para o ticker do Yahoo com sufixo, quando necessário."""
    s = (symbol or "").strip().upper()
    return YF_SYMBOL_MAP.get(s, s)


# -------------------------- HELPERS DE SERIES --------------------------------

def _ensure_series(close_obj) -> Optional[pd.Series]:
    """
    Normaliza o que vem em df['Close'] para uma Series.
    - Se vier DataFrame (MultiIndex/colunas extras), pega a última coluna não-vazia.
    - Se vier Series, retorna a própria.
    """
    if close_obj is None:
        return None
    if isinstance(close_obj, pd.Series):
        return close_obj
    if isinstance(close_obj, pd.DataFrame):
        # tenta a última coluna com dados válidos
        for col in reversed(close_obj.columns):
            col_s = close_obj[col].dropna()
            if not col_s.empty:
                return close_obj[col]
        # se todas vazias, devolve a última coluna mesmo (vai dar vazio depois)
        if close_obj.shape[1] > 0:
            return close_obj.iloc[:, -1]
        return None
    # formato inesperado
    return None


def _last_close_as_float_from_series(close_s: pd.Series) -> Optional[float]:
    """
    Extrai o último valor de uma Series de fechamento como float,
    sem FutureWarnings (usa .item() quando disponível).
    """
    s = close_s.dropna()
    if s.empty:
        return None
    val = s.iloc[-1]
    try:
        return float(getattr(val, "item", lambda: val)())
    except Exception:
        return float(val)


# -------------------------- PROVIDER -----------------------------------------

class YahooProvider(DataProvider):
    """
    Provider de dados do Yahoo com mapeamento regional.
    Métodos:
      - get_price(symbol)  → último Close (float) ou None
      - get_history(symbol, period, interval) → DataFrame OHLCV ou df vazio
    """

    def get_price(self, symbol: str) -> Optional[float]:
        t = resolve_symbol(symbol)
        try:
            # auto_adjust=False explícito para evitar mudanças de default no yfinance
            df = yf.download(
                t, period="5d", interval="1d",
                progress=False, auto_adjust=False, threads=True
            )
        except Exception:
            return None

        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        close_obj = df.get("Close")
        close_s = _ensure_series(close_obj)
        if close_s is None:
            return None

        return _last_close_as_float_from_series(close_s)

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        t = resolve_symbol(symbol)
        try:
            df = yf.download(
                t, period=period, interval=interval,
                progress=False, auto_adjust=False, threads=True
            )
        except Exception:
            return pd.DataFrame()

        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
