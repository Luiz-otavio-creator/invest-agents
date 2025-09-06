# common/providers/__init__.py
# -----------------------------------------------------------------------------
# Ponto único para preços e dados fundamentais/macros:
# - Cripto: CoinGecko (com fallback mock)
# - Ações/ETFs/REITs: Yahoo (com fallback estático)
# - Lote: batch_latest_price() (cripto em uma tacada só)
# - Fundamentals (AlphaVantage OVERVIEW) e macro (FRED) como antes
# -----------------------------------------------------------------------------

from typing import Dict, List, Optional

from common.providers.yahoo_provider import YahooProvider
from common.providers.coingecko_provider import CoinGeckoProvider
from common.providers.alphavantage_provider import AlphaVantageProvider
from common.providers.fred_provider import FredProvider

# Reaproveitamos utilidades robustas (mock/CG simples) já usadas no projeto
from common.utils.providers import cg_simple_prices, mock_price  # <- grátis e com fallback

_yf = YahooProvider()
_cg = CoinGeckoProvider()
_av = AlphaVantageProvider()
_fred = FredProvider()

_CRYPTO = {"BTC", "ETH", "SOL", "ADA", "DOGE"}

# Fallback estático para não-cripto (última linha = fallback genérico 100.0)
_FALLBACK_PRICE_MAP: Dict[str, float] = {
    # Equities/ETFs US/EU
    "VOO": 520.0, "QQQ": 470.0, "VGK": 70.0, "EZU": 55.0,
    "AAPL": 230.10, "MSFT": 415.30, "NVDA": 122.90, "GOOGL": 175.10, "AMZN": 190.75,
    "ASML": 1150.0, "LVMH": 730.0, "SAP": 200.0,
    # Bonds ETFs
    "IEF": 100.0, "TLT": 100.0, "SHY": 100.0, "IEGA": 100.0, "IEAC": 100.0, "LQD": 100.0,
    # REITs
    "VNQ": 90.0, "IPRP": 6.0, "PLD": 120.0, "O": 55.0, "SPG": 150.0,
}

def latest_price(symbol: str) -> Optional[float]:
    """
    Preço pontual com fallback:
      - Se símbolo ∈ CRYPTO → CoinGecko → mock_price
      - Senão → Yahoo → _FALLBACK_PRICE_MAP → 100.0
    Retorna float > 0 quando houver preço; caso contrário, 100.0 como último recurso.
    """
    if not symbol:
        return None
    sym = symbol.strip().upper()

    # 1) Cripto
    if sym in _CRYPTO:
        # Tenta provider de cripto (que por sua vez usa CG)
        try:
            p = _cg.get_price(sym)  # ok se tua CoinGeckoProvider expõe get_price
            if p and float(p) > 0:
                return float(p)
        except Exception:
            pass
        # 2) fallback por utilitário com backoff (chamada em lote lá dentro)
        try:
            m = cg_simple_prices([sym])
            v = m.get(sym)
            if v and float(v) > 0:
                return float(v)
        except Exception:
            pass
        # 3) fallback final mock
        return float(mock_price(sym))

    # 2) Não-cripto → Yahoo
    try:
        p = _yf.get_price(sym)
        if p and float(p) > 0:
            return float(p)
    except Exception:
        pass

    # 3) fallback estático → genérico 100.0
    return float(_FALLBACK_PRICE_MAP.get(sym, 100.0))


def batch_latest_price(symbols: List[str]) -> Dict[str, float]:
    """
    Preços em lote:
      - Cripto: uma chamada ao cg_simple_prices (economiza rate limit)
      - Não-cripto: Yahoo por símbolo (yfinance não lida bem com mix em lote)
      - Fallbacks idem ao latest_price()
    """
    out: Dict[str, float] = {}
    syms = [s.strip().upper() for s in symbols if s]

    cryptos = [s for s in syms if s in _CRYPTO]
    others  = [s for s in syms if s not in _CRYPTO]

    # 1) Lote de cripto
    if cryptos:
        priced = None
        try:
            priced = cg_simple_prices(cryptos)
        except Exception:
            priced = {}

        for s in cryptos:
            v = (priced or {}).get(s)
            if v and float(v) > 0:
                out[s] = float(v)
            else:
                # tenta provider direto
                try:
                    p = _cg.get_price(s)
                    if p and float(p) > 0:
                        out[s] = float(p)
                        continue
                except Exception:
                    pass
                out[s] = float(mock_price(s))  # fallback final

    # 2) Não-cripto (um a um) com fallback
    for s in others:
        try:
            p = _yf.get_price(s)
            if p and float(p) > 0:
                out[s] = float(p)
                continue
        except Exception:
            pass
        out[s] = float(_FALLBACK_PRICE_MAP.get(s, 100.0))

    return out


def fundamentals(symbol: str) -> Dict:
    """AlphaVantage OVERVIEW (grátis) com cache da tua AlphaVantageProvider."""
    try:
        return _av.get_fundamentals(symbol) or {}
    except Exception:
        return {}


def macro_series(series_id: str):
    """FRED (grátis), devolve pandas DataFrame conforme tua FredProvider."""
    return _fred.get_macro_series(series_id)
