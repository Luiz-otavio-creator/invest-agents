# agents/fixed_income/agent.py (real-time + macro via FRED)
# -----------------------------------------------------------------------------
# O que este agente faz agora:
# 1) Continua usando preços/histórico dos ETFs (Yahoo) para um proxy de yield do ETF.
# 2) Consulta o FRED (grátis) para:
#    - DGS10  → Treasury 10Y yield (nível de juros "risk-free")
#    - BAMLH0A0HYM2 → High Yield OAS (proxy de estresse/spread de crédito)
# 3) Compõe um "approx_yield" mais realista:
#       approx_yield = etf_yield + 0.5 * yield_proxy - 0.3 * spread_proxy
#    E penaliza duration longe do alvo (TARGET_DUR).
# 4) Emite sinais com rationale claro (inclui números).
#
# Correções nesta versão:
# - Normalização robusta do campo Close (pode vir como DataFrame ou Series no yfinance).
# - Sem FutureWarnings (usa .item()/iloc).
# - Tolerante a falhas do FRED (defaults).
# -----------------------------------------------------------------------------

import os
import datetime
from typing import Optional
import pandas as pd

from common.utils.bus import publish
from common.utils.providers import yf_history  # do seu projeto
from common.providers import macro_series      # FRED provider do seu projeto

OUT = "out/signals_fixed_income.json"

# ETFs de RF (USD/EUR)
BOND_ETFS = [
    "IEF", "TLT", "SHY",   # UST curvas
    "LQD",                 # USD IG Corporate
    "IEAC", "IEGA"         # EUR IG / EUR Gov (mapeados no providers)
]

# Durations "típicas" (aprox.) para penalização
DUR = { "IEF": 7.5, "TLT": 18.0, "SHY": 2.0, "LQD": 8.5, "IEAC": 6.0, "IEGA": 7.0 }
TARGET_DUR = 6.0

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

# ---------------------- helpers de série FRED (grátis) -----------------------

def _fred_last(series_id: str) -> Optional[float]:
    """
    Lê a série do FRED via provider e retorna o último valor válido como float.
    Ex.: DGS10 retorna ~ 4.20 (que representa 4.20%).
    """
    try:
        df = macro_series(series_id)  # DataFrame com colunas ["date","value"]
        if not isinstance(df, pd.DataFrame) or df.empty or "value" not in df.columns:
            return None
        s = pd.to_numeric(df["value"], errors="coerce").dropna()
        if s.empty:
            return None
        try:
            return float(s.tail(1).item())
        except Exception:
            return float(s.iloc[-1])
    except Exception:
        return None

def fred_yield_pct(series_id: str) -> Optional[float]:
    """Retorna yield do FRED em FRAÇÃO (0.042 = 4.2%)."""
    v = _fred_last(series_id)
    if v is None:
        return None
    return float(v) / 100.0

def fred_spread_pct(series_id: str) -> Optional[float]:
    """Retorna spread em FRAÇÃO (0.025 = 2.5%)."""
    v = _fred_last(series_id)
    if v is None:
        return None
    return float(v) / 100.0

# --------------------------- helpers de preço (Yahoo) ------------------------

def _close_series(df: pd.DataFrame) -> Optional[pd.Series]:
    """
    Normaliza o que vem em df['Close'] para uma Series.
    - Se vier Series, retorna a própria.
    - Se vier DataFrame (MultiIndex/colunas extras), pega a última coluna não-vazia.
    """
    if df is None or df.empty:
        return None
    close_obj = df.get("Close")
    if close_obj is None:
        return None
    if isinstance(close_obj, pd.Series):
        return close_obj
    if isinstance(close_obj, pd.DataFrame):
        # tenta a última coluna com dados válidos
        for col in reversed(close_obj.columns):
            col_s = pd.to_numeric(close_obj[col], errors="coerce").dropna()
            if not col_s.empty:
                return close_obj[col]
        # fallback: qualquer coluna (pode estar vazia; trataremos adiante)
        if close_obj.shape[1] > 0:
            return close_obj.iloc[:, -1]
        return None
    return None

def _last_close(df: pd.DataFrame) -> Optional[float]:
    s = _close_series(df)
    if s is None:
        return None
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return None
    try:
        return float(s.tail(1).item())
    except Exception:
        return float(s.iloc[-1])

def _first_close(df: pd.DataFrame) -> Optional[float]:
    s = _close_series(df)
    if s is None:
        return None
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return None
    try:
        return float(s.head(1).item())
    except Exception:
        return float(s.iloc[0])

def etf_yield_proxy_12m(ticker: str) -> float:
    """
    Proxy simples de 'yield' com base no retorno de 12 meses do preço (não é SEC yield).
    Mantemos este componente como parte do blend, somente para ranking relativo.
    """
    df = yf_history(ticker, period="1y", interval="1d")
    if df is None or df.empty:
        return 0.03  # fallback conservador
    p0 = _first_close(df)
    p1 = _last_close(df)
    if p0 is None or p1 is None or p0 <= 0:
        return 0.03
    ret_12m = (p1 / p0) - 1.0
    # Limitamos para evitar extremos e manter escala de "yield"
    return float(max(0.0, min(0.08, 0.03 + ret_12m / 3.0)))

# ------------------------------- scoring -------------------------------------

def score_bond_etf(ticker: str):
    """
    Blend macro + ETF:
      yield_proxy   = DGS10 (risk-free em fração)
      spread_proxy  = HY OAS (estresse de crédito em fração)
      etf_yield     = proxy via preço 12m (acima)
      approx_yield  = etf_yield + 0.5 * yield_proxy - 0.3 * spread_proxy
      score         = 0.5 + 4*(approx_yield - 3%) - penalty(duration)
    """
    # 1) proxies macro (com tolerância a falhas)
    y_rf = fred_yield_pct("DGS10")            # ex.: 0.042
    hy_oas = fred_spread_pct("BAMLH0A0HYM2")  # ex.: 0.025
    if y_rf is None:   y_rf = 0.04   # fallback
    if hy_oas is None: hy_oas = 0.02 # fallback

    # 2) proxy baseado no próprio ETF
    y_etf = etf_yield_proxy_12m(ticker)

    # 3) composição do "approx_yield"
    approx_yield = y_etf + 0.5 * y_rf - 0.3 * hy_oas

    # 4) penalização por duration longe do alvo
    dur = DUR.get(ticker, TARGET_DUR)
    dur_pen = 0.015 * (dur - TARGET_DUR) ** 2  # parábola suave

    # 5) score final (clamp em [0,1])
    base = 4.0 * (approx_yield - 0.03)  # "rende" a partir de 3% anual
    raw = base - dur_pen
    s = clamp(0.5 + raw, 0.0, 1.0)

    side = "BUY" if s >= 0.55 else "HOLD"
    return {
        "instrument_id": ticker,
        "side": side,
        "confidence": round(s, 3),
        "rationale": (
            f"approx_yield={approx_yield:.2%}; "
            f"DGS10={y_rf:.2%}; HY_OAS={hy_oas:.2%}; dur~{dur}"
        ),
        "ttl_days": 30,
        "collected_at": datetime.datetime.utcnow().isoformat()
    }

# ------------------------------- main ----------------------------------------

def main():
    os.makedirs("out", exist_ok=True)
    signals = [score_bond_etf(t) for t in BOND_ETFS]
    publish(OUT, signals)
    print(f"[fixed_income] {len(signals)} sinais salvos em {OUT} (Yahoo + FRED)")

if __name__ == "__main__":
    main()
