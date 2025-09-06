# common/utils/providers.py
# -----------------------------------------------------------------------------
# Utilitários de provedores (gratuitos) com cache + backoff
#
# O que inclui:
# - Yahoo Finance: último preço e histórico (com mapeamento de tickers EU/UK)
# - CoinGecko: preços simples e histórico diário (com cache + retry/backoff)
# - Fallbacks (mock) quando APIs falham ou estão rate-limited
# - Helpers de conveniência (SMA)
#
# Requisitos:
# - yfinance, requests, pandas, numpy
# - common/cache/cache.py (FileCache) e common/settings.py (SETTINGS)
#
# Observação:
# - o cache reduz chamadas repetidas e alivia rate limits do CoinGecko
# -----------------------------------------------------------------------------

import datetime as dt
import time
import random
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf

# Cache/Settings do projeto
try:
    from common.cache.cache import FileCache
    from common.config.settings import SETTINGS
    _cache = FileCache("out/cache")
except Exception:
    # fallback (sem cache, se módulos ainda não existirem)
    _cache = None
    class _Dummy:
        ttl_price = 900
        ttl_intraday = 300
        ttl_fundamentals = 30*24*3600
        ttl_macro = 86400
    SETTINGS = _Dummy()

# ==============================
# Yahoo Finance helpers
# ==============================

# Mapeia tickers "sem sufixo" para o símbolo do Yahoo quando necessário (Europa/UK)
YF_SYMBOL_MAP = {
    # REITs/ETFs Europe
    "IPRP": "IPRP.L",   # iShares Developed Property UCITS ETF (LSE)
    # Equities Europe (exemplos do seu universo)
    "ASML": "ASML.AS",
    "LVMH": "MC.PA",
    "SAP":  "SAP.DE",
    # Bonds UCITS (ajuste conforme necessário)
    "IEAC": "IEAC.MI",  # iShares Euro Corp Bond (Borsa Italiana)
    "IEGA": "IEGA.L",   # iShares Euro Govt Bond (LSE)
}

def resolve_yf_symbol(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    return YF_SYMBOL_MAP.get(t, t)

def _last_scalar(series: pd.Series) -> Optional[float]:
    """Extrai o último valor como float, sem FutureWarning."""
    if series is None:
        return None
    s = pd.Series(series).dropna()
    if s.empty:
        return None
    try:
        return float(s.tail(1).item())
    except Exception:
        return float(s.iloc[-1])

def _first_scalar(series: pd.Series) -> Optional[float]:
    """Extrai o primeiro valor como float, sem FutureWarning."""
    if series is None:
        return None
    s = pd.Series(series).dropna()
    if s.empty:
        return None
    try:
        return float(s.head(1).item())
    except Exception:
        return float(s.iloc[0])

def yf_latest_price(tickers: List[str]) -> Dict[str, float]:
    """
    Último preço de fechamento por ticker (com mapeamento EU/UK).
    Retorna {ticker_original: close_float}
    """
    out: Dict[str, float] = {}
    if not tickers:
        return out

    # mapa para reverter símbolo yfinance -> símbolo "orig"
    resolved = {t: resolve_yf_symbol(t) for t in tickers}
    reverse_map = {v: k for k, v in resolved.items()}

    # yfinance aceita lista separada por espaço
    data = yf.download(
        " ".join(resolved.values()),
        period="5d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    # data pode ser MultiIndex (coluna nível 1 = ticker yfinance)
    def pick_last_close(series: pd.Series) -> Optional[float]:
        return _last_scalar(series)

    if isinstance(data, pd.DataFrame) and not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            # data["Close"] é DataFrame (colunas = tickers yfinance)
            if "Close" in data:
                for t_yf in data["Close"].columns:
                    price = pick_last_close(data["Close"][t_yf])
                    orig = reverse_map.get(t_yf, t_yf)  # volta para ticker original
                    if price is not None:
                        out[orig] = price
        else:
            # um único ativo
            price = pick_last_close(data.get("Close"))
            if price is not None:
                # mapeia para o primeiro ticker original
                out[tickers[0]] = price

    return out

def yf_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    t = resolve_yf_symbol(ticker)
    df = yf.download(
        t, period=period, interval=interval,
        auto_adjust=False, progress=False, threads=True
    )
    return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()

def yf_dividend_yield_ttm(ticker: str) -> Optional[float]:
    """Dividend yield TTM aproximado: soma de dividendos 12m / último close."""
    t = resolve_yf_symbol(ticker)
    tk = yf.Ticker(t)
    try:
        divs = tk.dividends  # pandas Series
        if divs is None or divs.empty:
            y = tk.info.get("dividendYield", None)
            return float(y) if y is not None else None
        last_12m_cut = (pd.Timestamp.utcnow() - pd.Timedelta(days=365)).tz_localize(None)
        ttm = float(divs[divs.index.tz_localize(None) >= last_12m_cut].sum())
        price = yf_latest_price([ticker]).get(ticker)
        if price and price > 0:
            return ttm / price
    except Exception:
        pass
    # fallback info
    try:
        y = tk.info.get("dividendYield", None)
        return float(y) if y is not None else None
    except Exception:
        return None

def yf_pe_ratio(ticker: str, default: float = 22.0) -> float:
    t = resolve_yf_symbol(ticker)
    tk = yf.Ticker(t)
    pe = tk.info.get("trailingPE", None)
    try:
        return float(pe) if pe is not None and np.isfinite(pe) else default
    except Exception:
        return default

# ==============================
# CoinGecko helpers (crypto)
# ==============================

CG_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
}

def mock_price(symbol: str) -> float:
    """Fallback simples para quando API do CoinGecko falhar."""
    base = {
        "BTC": 50000.0,
        "ETH": 2500.0,
        "SOL": 150.0,
        "ADA": 0.40,
        "DOGE": 0.10,
    }
    return round(base.get(symbol.upper(), 100.0) * (0.95 + 0.10 * random.random()), 6)

def _cache_get(key: str):
    if _cache is None:
        return None
    try:
        return _cache.get(key)
    except Exception:
        return None

def _cache_set(key: str, value, ttl: int):
    if _cache is None:
        return
    try:
        _cache.set(key, value, ttl)
    except Exception:
        pass

def _cg_request(url: str, params: dict, ttl: int, max_retries: int = 3, backoff: int = 2):
    """
    Request robusto ao CoinGecko com cache + retries/backoff.
    - Cache: key = URL + params (stringificados)
    - Retries: backoff exponencial com jitter
    """
    key = f"CG::{url}::{sorted(params.items())}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                _cache_set(key, data, ttl)
                return data
            elif r.status_code in (401, 403, 429):
                wait = (backoff ** attempt) + random.random()
                print(f"[crypto] CoinGecko {r.status_code}. Retry em {wait:.1f}s...")
                time.sleep(wait)
                continue
            else:
                # status inesperado: sem exceção dura; devolve {}
                print(f"[crypto] HTTP {r.status_code} CoinGecko (url={url}).")
                return {}
        except Exception as e:
            print(f"[crypto] exceção CoinGecko: {e}")
            time.sleep(backoff)
    return {}

def cg_simple_prices(symbols: List[str], vs: str = "usd") -> Dict[str, float]:
    """
    Preços simples (spot) para símbolos cripto. Usa cache + backoff.
    Fallback: mock_price quando faltarem itens.
    """
    ids = [CG_IDS[s] for s in symbols if s in CG_IDS]
    if not ids:
        return {}

    url = "https://api.coingecko.com/api/v3/simple/price"
    data = _cg_request(
        url,
        {"ids": ",".join(ids), "vs_currencies": vs},
        ttl=getattr(SETTINGS, "ttl_price", 900)
    )

    out: Dict[str, float] = {}
    if not isinstance(data, dict) or not data:
        # fallback total
        return {s: mock_price(s) for s in symbols}

    for s in symbols:
        k = CG_IDS.get(s)
        v = None
        try:
            if k and k in data and isinstance(data[k], dict) and vs in data[k]:
                v = float(data[k][vs])
        except Exception:
            v = None
        out[s] = v if (v is not None and v > 0) else mock_price(s)
    return out

def cg_history_daily(symbol: str, days: int = 400) -> pd.DataFrame:
    """
    Histórico diário (close) de preço em USD para uma cripto.
    Usa cache + backoff. Em falha grave, retorna DataFrame vazio.
    """
    cid = CG_IDS.get(symbol.upper())
    if not cid:
        return pd.DataFrame()

    url = f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart"
    data = _cg_request(
        url,
        {"vs_currency": "usd", "days": days},
        ttl=getattr(SETTINGS, "ttl_price", 900)
    )
    prices = data.get("prices", []) if isinstance(data, dict) else []
    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(prices, columns=["ts", "price"])
    # timestamps em ms
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(None)
    df.set_index("ts", inplace=True)
    return df

# ==============================
# Conveniência
# ==============================

def sma(series: pd.Series, window: int) -> Optional[float]:
    """Média móvel simples com proteção para séries curtas."""
    if series is None:
        return None
    s = pd.Series(series).dropna()
    if len(s) < window:
        return None
    return float(s.tail(window).mean())
