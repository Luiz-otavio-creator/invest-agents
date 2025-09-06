"""
features/base_features.py
-------------------------
Biblioteca de features (gratuito) para equities.

Inclui:
- Preço (yfinance): retornos 1/3/6/12m, volatilidade EWMA, drawdown, beta vs benchmark (ex.: VOO/VGK).
- Técnicos: SMA(20/50/200), RSI(14), MACD(12,26,9) rápido.
- Fundamental (AlphaVantage via common.providers.fundamentals):
    PE, PB, ROE, margem operacional/líquida, FCF/Revenue, Debt/EBITDA, crescimento (receita/EPS).
- Macro (FRED via common.providers.macro_series):
    DGS2, DGS10, BAMLH0A0HYM2 (High Yield spread) com lag de 1 dia para evitar look-ahead.
- Setoriais: dummies GICS sector/industry; região.
- Limpeza: winsorizar p5/p95 e padronizar (z-score) por setor/região (opcional).

Observações importantes:
- Todas as funções assumem que você já respeitou a cronologia (nada de olhar o futuro).
- As features retornadas são *do último ponto da série* (t), usando apenas dados até t.
- Para evitar look-ahead em macro, aplicamos lag de 1 dia nas séries FRED.

Dependências externas esperadas (camada de providers):
    from common.providers import fundamentals, macro_series
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Iterable, Tuple
import numpy as np
import pandas as pd

# ==========================
# Utilidades genéricas
# ==========================

def winsorize(s: pd.Series, p_low: float = 0.05, p_high: float = 0.95) -> pd.Series:
    """
    Recorta caudas em percentis (ex.: 5% e 95%).
    Mantém índice; ignora NaN (propaga NaN onde já existia).
    """
    s = s.copy()
    q_low, q_high = s.quantile(p_low), s.quantile(p_high)
    return s.clip(lower=q_low, upper=q_high)

def zscore(s: pd.Series) -> pd.Series:
    """
    Z-score padrão com ddof=0.
    Se desvio padrão = 0, retorna 0s (evita inf/NaN).
    """
    mu = s.mean()
    sd = s.std(ddof=0)
    if sd == 0 or pd.isna(sd):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd

def merge_feature_blocks(blocks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Mescla dicionários de features, prefixando chaves com o nome do bloco.
    Ex.: {"tech":{"rsi":50}} -> {"tech__rsi":50}
    """
    out: Dict[str, Any] = {}
    for prefix, d in blocks.items():
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            key = f"{prefix}__{k}" if prefix else k
            out[key] = v
    return out

def _pct_return(series: pd.Series, lag: int) -> float:
    s = series.dropna()
    if len(s) <= lag:
        return np.nan
    try:
        return float(s.iloc[-1] / s.iloc[-lag-1] - 1.0)
    except Exception:
        return np.nan

def _ewma_vol(series: pd.Series, span: int = 21) -> float:
    s = series.dropna().pct_change()
    if len(s) < 2:
        return np.nan
    return float(s.ewm(span=span, adjust=False).std().iloc[-1])

def _max_drawdown(series: pd.Series) -> float:
    """
    Drawdown máximo até t (em % negativo). Retorna número negativo (ex.: -0.35).
    """
    s = series.dropna()
    if s.empty:
        return np.nan
    roll_max = s.cummax()
    dd = s / roll_max - 1.0
    return float(dd.min())

def _beta_vs_benchmark(asset_px: pd.Series, bench_px: pd.Series, window: int = 126) -> float:
    """
    Beta = Cov(Ra, Rm)/Var(Rm) usando janelas diárias (~6m úteis).
    """
    a = asset_px.dropna().pct_change()
    b = bench_px.dropna().pct_change()
    df = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna().tail(window)
    if len(df) < 20:
        return np.nan
    var_m = df["b"].var(ddof=0)
    if var_m == 0 or pd.isna(var_m):
        return np.nan
    cov = ((df["a"] - df["a"].mean()) * (df["b"] - df["b"].mean())).mean()
    return float(cov / var_m)

def _sma_gap(s: pd.Series, win: int) -> float:
    s = s.dropna()
    if len(s) < win:
        return np.nan
    sma = s.rolling(win).mean().iloc[-1]
    px = s.iloc[-1]
    return float(px / sma - 1.0) if sma and np.isfinite(sma) else np.nan

def _rsi_14(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 15:
        return np.nan
    r = s.diff().dropna()
    up = r.clip(lower=0).rolling(14).mean()
    dn = (-r.clip(upper=0)).rolling(14).mean()
    denom = dn.iloc[-1] if len(dn) else np.nan
    if denom and denom > 0:
        rs = float(up.iloc[-1] / denom)
        return 100.0 - (100.0 / (1.0 + rs))
    return np.nan

def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def _macd_fast(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    """
    MACD rápido estilo trading: EMA(fast)-EMA(slow), sinal=EMA(macd,9), hist=macd-sinal
    Retorna valores do último ponto.
    """
    s = s.dropna()
    if len(s) < slow + signal:
        return (np.nan, np.nan, np.nan)
    ema_fast = _ema(s, fast)
    ema_slow = _ema(s, slow)
    macd = ema_fast - ema_slow
    macd_signal = _ema(macd, signal)
    macd_hist = macd - macd_signal
    return float(macd.iloc[-1]), float(macd_signal.iloc[-1]), float(macd_hist.iloc[-1])

def lag_series(s: pd.Series, periods: int = 1) -> pd.Series:
    """
    Aplica lag (deslocamento para frente) para evitar look-ahead.
    Ex.: lag 1 dia -> valor de ontem para usar hoje.
    """
    return s.shift(periods)

# ==========================
# Blocos de features
# ==========================

def price_features(prices: pd.Series, bench_prices: Optional[pd.Series] = None) -> Dict[str, float]:
    """
    prices: Série de preços (fechamento ajustado) até t.
    bench_prices: Série do benchmark (ex.: VOO para EUA, VGK para Europa), opcional.
    """
    s = prices.dropna()
    ret_1m  = _pct_return(s, 21)   # ~1 mês útil
    ret_3m  = _pct_return(s, 63)
    ret_6m  = _pct_return(s, 126)
    ret_12m = _pct_return(s, 252)
    vol_21  = _ewma_vol(s, span=21)
    mdd     = _max_drawdown(s)
    beta    = _beta_vs_benchmark(s, bench_prices, window=126) if bench_prices is not None else np.nan

    return {
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_6m": ret_6m,
        "ret_12m": ret_12m,
        "vol_21d": vol_21,
        "max_drawdown": mdd,
        "beta_6m": beta,
    }

def technical_features(prices: pd.Series) -> Dict[str, float]:
    s = prices.dropna()
    sma20_gap  = _sma_gap(s, 20)
    sma50_gap  = _sma_gap(s, 50)
    sma200_gap = _sma_gap(s, 200)
    rsi14      = _rsi_14(s)
    macd, macd_sig, macd_hist = _macd_fast(s)
    return {
        "sma_20_gap": sma20_gap,
        "sma_50_gap": sma50_gap,
        "sma_200_gap": sma200_gap,
        "rsi_14": rsi14,
        "macd": macd,
        "macd_signal": macd_sig,
        "macd_hist": macd_hist,
    }

def fundamental_features(av_overview: Dict[str, Any]) -> Dict[str, float]:
    """
    Espera o dicionário normalizado vindo de common.providers.alphavantage_provider.get_fundamentals().
    Campos esperados (podem faltar → NaN):
      pe, pb, roe, profit_margin, operating_margin, fcf_revenue, debt_ebitda, rev_growth, eps_growth
    """
    def fget(k):
        v = av_overview.get(k, None)
        try:
            return float(v) if v is not None else np.nan
        except Exception:
            return np.nan

    return {
        "pe": fget("pe"),
        "pb": fget("pb"),
        "roe": fget("roe"),
        "profit_margin": fget("profit_margin"),
        "operating_margin": fget("operating_margin"),
        "fcf_revenue": fget("fcf_revenue"),
        "debt_ebitda": fget("debt_ebitda"),
        "rev_growth": fget("rev_growth"),
        "eps_growth": fget("eps_growth"),
    }

def macro_features(dgs2: pd.Series, dgs10: pd.Series, hy_spread: pd.Series) -> Dict[str, float]:
    """
    Aplica lag(1) por segurança (não usar a leitura do DIA em que se está tomando decisão).
    Retorna último valor disponível (lagged).
    """
    def last_lag1(s: pd.Series) -> float:
        sl = lag_series(s.dropna(), periods=1).dropna()
        return float(sl.iloc[-1]) if len(sl) else np.nan

    return {
        "dgs2": last_lag1(dgs2),
        "dgs10": last_lag1(dgs10),
        "hy_spread": last_lag1(hy_spread),
        "term_spread": (last_lag1(dgs10) - last_lag1(dgs2)) if (len(dgs10.dropna()) and len(dgs2.dropna())) else np.nan,
    }

def sector_features(sector: Optional[str], industry: Optional[str], region: Optional[str]) -> Dict[str, float]:
    """
    Dummies simples (one-hot) — você pode manter um vocabulário controlado.
    Para MVP, retornamos as strings para o pipeline tabular one-hot-encode depois.
    """
    return {
        "sector": sector or "",
        "industry": industry or "",
        "region": region or "",
    }

# ==========================
# Limpeza / padronização (opcional no dataset)
# ==========================

def group_winsorize_zscore(df: pd.DataFrame, value_cols: Iterable[str], group_cols: Iterable[str]) -> pd.DataFrame:
    """
    Aplica winsorize + zscore por grupos (ex.: sector/region).
    Cria colunas novas com sufixo: __w (winsorized) e __z (zscored).
    """
    out = df.copy()
    group_cols = list(group_cols)
    for col in value_cols:
        wcol = f"{col}__w"
        zcol = f"{col}__z"
        if group_cols:
            out[wcol] = out.groupby(group_cols)[col].transform(lambda s: winsorize(s))
            out[zcol] = out.groupby(group_cols)[wcol].transform(lambda s: zscore(s))
        else:
            out[wcol] = winsorize(out[col])
            out[zcol] = zscore(out[wcol])
    return out

# ==========================
# Convenience: montar feature row único
# ==========================

def build_feature_row(
    prices: pd.Series,
    bench_prices: Optional[pd.Series],
    av_overview: Dict[str, Any],
    fred_dgs2: pd.Series,
    fred_dgs10: pd.Series,
    fred_hy_spread: pd.Series,
    sector: Optional[str],
    industry: Optional[str],
    region: Optional[str],
) -> Dict[str, Any]:
    """
    Monta um único dicionário de features para (ticker, t).
    """
    blocks = {
        "px":  price_features(prices, bench_prices),
        "tech": technical_features(prices),
        "fund": fundamental_features(av_overview),
        "macro": macro_features(fred_dgs2, fred_dgs10, fred_hy_spread),
        "meta": sector_features(sector, industry, region),
    }
    return merge_feature_blocks(blocks)
