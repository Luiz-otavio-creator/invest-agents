"""
ml/datasets/targets.py
----------------------
Alvos de treinamento (retorno futuro e/ou ranking).
"""
import pandas as pd
import numpy as np

def forward_return(prices: pd.Series, horizon_days: int = 21) -> float:
    """
    Retorno simples futuro em horizonte (t -> t+h). Assume prices até t+h **não** incluídos no dataset de treino.
    """
    s = prices.dropna()
    if len(s) <= horizon_days:
        return np.nan
    # último valor conhecido (t) e valor futuro (t+h)
    px_t = s.iloc[-horizon_days-1]
    px_f = s.iloc[-1]
    return float(px_f / px_t - 1.0)
