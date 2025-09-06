# agents/reits/agent.py (real-time)
import os, datetime
from math import log1p
from common.utils.bus import publish
from common.utils.providers import yf_dividend_yield_ttm

OUT = "out/signals_reits.json"

REITS = ["VNQ", "IPRP", "PLD", "O", "SPG"]
ETF_SET = {"VNQ", "IPRP"}
ETF_BOOST = 0.05

def clamp(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))

def score_reit(ticker: str):
    dy = yf_dividend_yield_ttm(ticker)
    if dy is None:  # sem DY → segurar
        dy = 0.0
    s = 0.5 + 0.8 * log1p(dy * 100) / 10.0
    if ticker in ETF_SET: s += ETF_BOOST
    s = clamp(s)
    return {
        "instrument_id": ticker,
        "side": "BUY" if s > 0.55 else "HOLD",
        "confidence": round(s, 3),
        "rationale": f"DY_TTM={dy:.2%}, ETFBoost={ticker in ETF_SET}",
        "ttl_days": 30,
        "collected_at": datetime.datetime.utcnow().isoformat()
    }

def main():
    os.makedirs("out", exist_ok=True)
    signals = [score_reit(t) for t in REITS]
    publish(OUT, signals)
    print(f"[reits] {len(signals)} sinais salvos em {OUT} (yfinance)")

if __name__ == "__main__":
    main()
