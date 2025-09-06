"""
ml/datasets/build_equities.py
-----------------------------
Esqueleto de montagem de dataset tabular para equities (MVP).
- Lê preços históricos (yfinance ou sua camada providers).
- Calcula features técnicas simples (features/base_features.py).
- Calcula target de retorno futuro 21d (ml/datasets/targets.py).
- Salva parquet em ml/datasets/equities_dataset.parquet

Você vai ligar isto à sua camada de providers conforme evoluir.
"""

import os
from pathlib import Path
from typing import List, Dict
import pandas as pd
import numpy as np

from features.base_features import simple_tech_features, merge_feature_blocks
from ml.datasets.targets import forward_return

OUT_PATH = Path("ml/datasets/equities_dataset.parquet")

def build_from_memory(price_panel: Dict[str, pd.Series], tickers: List[str]) -> pd.DataFrame:
    """
    price_panel: dict[ticker] -> Series de preços ajustados (índice datetime, ASC, <= t)
    """
    rows = []
    for t in tickers:
        s = price_panel.get(t, pd.Series(dtype=float))
        if s is None or len(s) < 80:
            continue
        feats = simple_tech_features(s)
        y = forward_return(s, horizon_days=21)
        row = {"ticker": t, "date": s.index[-1].strftime("%Y-%m-%d")}
        row.update(merge_feature_blocks({"tech": feats}))
        row["target_21d"] = y
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["date", "ticker"], inplace=True)
    return df

def main():
    os.makedirs("ml/datasets", exist_ok=True)
    # 🔧 Aqui você passa o painel de preços (ex.: coletado via providers).
    # Por enquanto, criamos um exemplo sintético para não quebrar.
    dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=250, freq="B")
    def synth():
        x = np.linspace(0, 1, len(dates))
        return pd.Series(100*(1+0.15*x+0.05*np.sin(10*x)), index=dates)
    panel = {
        "AAPL": synth(),
        "MSFT": synth()*1.02,
        "NVDA": synth()*1.10,
    }
    df = build_from_memory(panel, ["AAPL","MSFT","NVDA"])
    df.to_parquet(OUT_PATH, index=False)
    print(f"[build_equities] Salvo: {OUT_PATH} | shape={df.shape}")

if __name__ == "__main__":
    main()
