# common/risk/risk.py
from typing import List, Dict
import math

def cap_position_weights(weights: Dict[str, float], max_pct: float) -> Dict[str, float]:
    capped = {}
    for k, w in weights.items():
        capped[k] = min(w, max_pct)
    # Renormaliza para somar 1 (se houve cortes).
    s = sum(capped.values())
    if s == 0:
        return capped
    return {k: v / s for k, v in capped.items()}

def within_band(current: float, target: float, band: float) -> bool:
    return (target - band) <= current <= (target + band)

def clamp_to_bands(current: float, target: float, band: float) -> float:
    if current < target - band:
        return target - band
    if current > target + band:
        return target + band
    return current

def simple_portfolio_metrics(positions: Dict[str, float]) -> Dict[str, float]:
    # Dummy metrics para MVP (substitua por cálculo real de vol/Sharpe no futuro).
    # Aqui retornamos apenas soma e concentração (HHI) para checagens rápidas.
    total = sum(positions.values())
    hhi = sum((v/total)**2 for v in positions.values()) if total > 0 else 0.0
    return {"gross_value": total, "hhi": hhi}
