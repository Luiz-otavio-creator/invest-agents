"""
ml/utils/splits.py
------------------
Funções de split temporal para evitar vazamento.
"""
import pandas as pd
from typing import Tuple

def time_split(df: pd.DataFrame, dt_col: str, train_end: str, valid_end: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df[dt_col] <= train_end].copy()
    valid = df[(df[dt_col] > train_end) & (df[dt_col] <= valid_end)].copy()
    test  = df[df[dt_col] > valid_end].copy()
    return train, valid, test
