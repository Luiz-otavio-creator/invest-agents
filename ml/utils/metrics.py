"""
ml/utils/metrics.py
-------------------
Métricas de ranking/regressão + utilidades de avaliação.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from typing import Dict

def information_coefficient(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Spearman rank correlation (IC)."""
    if len(y_true) < 3:
        return np.nan
    r, _ = spearmanr(y_true, y_pred)
    return float(r)

def top_bottom_spread(df: pd.DataFrame, pred_col: str, ret_col: str, q: float = 0.1) -> float:
    """
    Calcula média de retornos do top decile menos bottom decile por janela (cross-section),
    depois faz média ao longo do tempo.
    df precisa conter colunas: ['date', pred_col, ret_col]
    """
    out = []
    for dt, g in df.groupby("date"):
        if len(g) < 10: 
            continue
        thr_top = g[pred_col].quantile(1-q)
        thr_bot = g[pred_col].quantile(q)
        top = g[g[pred_col] >= thr_top][ret_col].mean()
        bot = g[g[pred_col] <= thr_bot][ret_col].mean()
        if pd.notna(top) and pd.notna(bot):
            out.append(top - bot)
    return float(np.nanmean(out)) if out else np.nan
