# tests/test_features.py
import pandas as pd
import numpy as np

from features.base_features import winsorize, zscore, merge_feature_blocks

def test_winsorize_basic():
    s = pd.Series([0, 1, 2, 100])
    w = winsorize(s, 0.25, 0.75)
    # p25=0.75, p75=2.5 -> recorta 0->0.75 e 100->2.5
    assert np.isclose(w.iloc[0], 0.75)
    assert np.isclose(w.iloc[-1], 2.5)
    # meio deve manter ordem relativa
    assert w.iloc[1] <= w.iloc[2]

def test_zscore_basic():
    s = pd.Series([1.0, 2.0, 3.0])
    z = zscore(s)
    assert np.isclose(z.mean(), 0.0)
    assert np.isclose(z.std(ddof=0), 1.0)

def test_merge_feature_blocks_no_nan_blast():
    blocks = {
        "a": {"x": 1.0, "y": np.nan},
        "b": {"z": 2.0}
    }
    m = merge_feature_blocks(blocks)
    # chaves com prefixo e sem explosão de NaNs inesperados
    assert "a__x" in m and "a__y" in m and "b__z" in m
    # apenas 3 chaves esperadas
    assert len(m.keys()) == 3
