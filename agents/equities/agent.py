# agents/equities/agent.py
# -----------------------------------------------------------------------------
# Agente de AÇÕES (US/EU) — tempo real (gratuito)
#
# O que este agente faz:
# 1) Histórico 12m via Yahoo (yfinance, camada YahooProvider) → momentum_12m.
# 2) Fundamentais via AlphaVantage OVERVIEW (FileCache/TTL) → PE, ROE, margens,
#    Debt/EBITDA, crescimento de receitas (rev_growth) e de EPS (eps_growth).
# 3) Score multifatorial simples e transparente:
#       score = clamp(0.5 + (sinais_positivos - penalidades), 0, 1)
#    Positivos: momentum, ROE, margens, rev_growth, eps_growth (+ ETF boost)
#    Penalidades: valuation (PE alto), endividamento (Debt/EBITDA elevado)
# 4) Emite sinais BUY/HOLD com rationale detalhado.
#
# Observações:
# - Sem FutureWarnings: extraímos escalares com .item() ao invés de float(Series).
# - Depende de:
#     - common/providers/yahoo_provider.py  (YahooProvider)
#     - common/providers/alphavantage_provider.py (fundamentals)
#     - common/utils/bus.py  (publish)
# - Se algum fundamental vier ausente (None), o termo vira 0 e o rationale mostra n/a.
# -----------------------------------------------------------------------------

import os
import datetime as dt
from typing import Optional, Dict, List

import pandas as pd

from common.utils.bus import publish
from common.providers.yahoo_provider import YahooProvider
from common.providers import fundamentals  # AlphaVantage OVERVIEW normalizado (com cache)

OUT = "out/signals_equities.json"

# Universo US/EU (pode ampliar/ler de CSV)
TICKERS: List[str] = [
    "VOO", "QQQ", "VGK", "EZU",           # ETFs US/EU
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "ASML", "LVMH", "SAP"                 # EU blue chips
]

# ETFs com leve boost (estabilidade/diversificação)
ETF_SET = {"VOO", "QQQ", "VGK", "EZU"}
ETF_BOOST = 0.06

# Provider único para Yahoo (histórico/preço)
_yf = YahooProvider()


# -------------------------- helpers sem FutureWarnings ------------------------

def _series_last_float(s: pd.Series) -> Optional[float]:
    """Extrai último valor de uma Series como float, sem FutureWarnings."""
    s = s.dropna()
    if s.empty:
        return None
    try:
        return float(s.tail(1).item())
    except Exception:
        return float(s.iloc[-1])

def _series_first_float(s: pd.Series) -> Optional[float]:
    """Extrai primeiro valor de uma Series como float, sem FutureWarnings."""
    s = s.dropna()
    if s.empty:
        return None
    try:
        return float(s.head(1).item())
    except Exception:
        return float(s.iloc[0])

def _last_close(df: pd.DataFrame) -> Optional[float]:
    """Último Close como float (ou None)."""
    if df is None or df.empty or "Close" not in df.columns:
        return None
    return _series_last_float(df["Close"])

def _first_close(df: pd.DataFrame) -> Optional[float]:
    """Primeiro Close como float (ou None)."""
    if df is None or df.empty or "Close" not in df.columns:
        return None
    return _series_first_float(df["Close"])

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def _val(x, default=0.0) -> float:
    """Converte None→default (para termos multiplicativos/adições)."""
    return default if x is None else float(x)

def _cap(x: Optional[float], lo: float, hi: float) -> float:
    """Recorta um valor (ou None→0) no intervalo [lo, hi] e retorna o próprio valor capado."""
    if x is None:
        return 0.0
    return max(lo, min(hi, float(x)))


# ------------------------------ engine de score ------------------------------

def score_equity(ticker: str) -> Dict:
    """
    Score multifatorial (MVP, 100% grátis) — transparente e robusto a faltas:
      Sinais positivos (cap e pesos):
        + momentum_12m_capped      → cap ∈ [-30%, +60%]     peso ~ 1.00x
        + 0.5 * min(ROE, 50%)      → ROE boost (qualidade)
        + 0.3 * min(OpMargin, 40%) → eficiência operacional
        + 0.2 * min(ProfitMargin,40%)
        + 0.4 * cap(rev_growth, -20%..+50%)
        + 0.4 * cap(eps_growth, -20%..+50%)
      Penalidades:
        - 0.20 * (PE / 25)         → valuation caro
        - debt_penalty             → endividamento (Debt/EBITDA > 2 penaliza)
      Normalização:
        score = clamp(0.5 + soma(sinais) - soma(penalidades), 0, 1)
      ETF boost:
        score += 0.06 para VOO/QQQ/VGK/EZU (clamp a 1.0)
    """
    # 1) Histórico 12m para momentum
    hist = _yf.get_history(ticker, period="1y", interval="1d")
    if hist is None or hist.empty or "Close" not in hist.columns:
        return {
            "instrument_id": ticker,
            "side": "HOLD",
            "confidence": 0.50,
            "rationale": "sem histórico yfinance",
            "ttl_days": 14,
            "collected_at": dt.datetime.utcnow().isoformat()
        }

    p_last = _last_close(hist)
    p_first = _first_close(hist)
    if p_last is None or p_first is None or p_first <= 0:
        momentum_12m = 0.0
    else:
        momentum_12m = (p_last / p_first) - 1.0

    # 2) Fundamentais via AlphaVantage (com cache local/TTL)
    f = fundamentals(ticker) or {}
    pe            = f.get("pe")
    roe           = f.get("roe")
    profit_margin = f.get("profit_margin")
    op_margin     = f.get("operating_margin")
    rev_growth    = f.get("rev_growth")      # ∆Receita
    eps_growth    = f.get("eps_growth")      # ∆EPS
    debt_ebitda   = f.get("debt_ebitda")

    # 3) Construção dos termos
    # Momentum cap: evita que outliers distorçam ([-30%, +60%])
    mom_cap = _cap(momentum_12m, -0.30, 0.60) * 1.00

    # ROE até 50% vira boost 0.5 * ROE
    roe_term = 0.5 * min(_val(roe), 0.50)

    # Margens: mais oper. (eficiência) e líquida (qualidade) — saturam em 40%
    opm_term = 0.3 * min(_val(op_margin), 0.40)
    pm_term  = 0.2 * min(_val(profit_margin), 0.40)

    # Crescimentos: cap em [-20%, +50%] e escala 0.4x
    revg_term = 0.4 * _cap(rev_growth, -0.20, 0.50)
    epsg_term = 0.4 * _cap(eps_growth, -0.20, 0.50)

    # Penalidade por PE: referência 25x
    pe_penalty = 0.0
    if pe is not None and pe > 0:
        pe_penalty = 0.20 * (pe / 25.0)

    # Penalidade por endividamento: suave até 2x, cresce depois
    #   debt_penalty ~ 0 quando Debt/EBITDA ≤ 2
    #   sobe gradualmente de 2→6+
    debt_penalty = 0.0
    if debt_ebitda is not None and debt_ebitda > 2.0:
        # escala suave: (x-2)/4 cap 0..1 * 0.25
        debt_penalty = 0.25 * max(0.0, min(1.0, (float(debt_ebitda) - 2.0) / 4.0))

    # Agregação (transparente)
    positives = mom_cap + roe_term + opm_term + pm_term + revg_term + epsg_term
    penalties = pe_penalty + debt_penalty
    raw = positives - penalties

    score = _clamp(0.5 + raw, 0.0, 1.0)
    if ticker in ETF_SET:
        score = _clamp(score + ETF_BOOST, 0.0, 1.0)

    side = "BUY" if score > 0.55 else "HOLD"

    # 4) Rationale descritivo e legível
    def _fmt(x, pct=False):
        if x is None:
            return "n/a"
        try:
            return f"{x:.2%}" if pct else f"{x:.2f}"
        except Exception:
            return "n/a"

    rationale_bits = [
        f"mom12m={_fmt(momentum_12m, pct=True)}",
        f"PE={_fmt(pe)}",
        f"ROE={_fmt(roe, pct=True)}",
        f"PM={_fmt(profit_margin, pct=True)}",
        f"OM={_fmt(op_margin, pct=True)}",
        f"RevG={_fmt(rev_growth, pct=True)}",
        f"EPSG={_fmt(eps_growth, pct=True)}",
        f"Debt/EBITDA={_fmt(debt_ebitda)}",
        f"ETFBoost={ticker in ETF_SET}"
    ]

    return {
        "instrument_id": ticker,
        "side": side,
        "confidence": round(float(score), 3),
        "rationale": "; ".join(rationale_bits),
        "ttl_days": 14,
        "collected_at": dt.datetime.utcnow().isoformat()
    }


# -------------------------------- entrypoint ---------------------------------

def main():
    os.makedirs("out", exist_ok=True)
    signals = [score_equity(t) for t in TICKERS]
    publish(OUT, signals)
    print(f"[equities] {len(signals)} sinais salvos em {OUT} (yahoo + AlphaVantage fundamentals)")

if __name__ == "__main__":
    main()
