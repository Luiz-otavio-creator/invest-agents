"""
ml/trainers/equities_ranker.py
------------------------------
Treinador baseline (sklearn) para prever retorno 21d e usar como ranking.
Lê config em config/ml/equities_ranker.yaml e dataset em ml/datasets/equities_dataset.parquet
"""

import json
import joblib
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error

from ml.utils.seeds import fix_seeds
from ml.utils.metrics import information_coefficient, top_bottom_spread

CFG_PATH = Path("config/ml/equities_ranker.yaml")
DATA_PATH = Path("ml/datasets/equities_dataset.parquet")
MODEL_PATH = Path("ml/models/equities_ranker.joblib")
METRICS_PATH = Path("ml/models/equities_ranker.metrics.json")

def load_config() -> dict:
    import yaml
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    fix_seeds(42)
    cfg = load_config()
    df = pd.read_parquet(DATA_PATH)
    # Split temporal simples por data (MVP): 80% treina, 10% val, 10% teste.
    df = df.dropna(subset=["target_21d"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["date", "ticker"], inplace=True)
    # Features = todas colunas tech__*
    feat_cols = [c for c in df.columns if c.startswith("tech__")]
    X = df[feat_cols].values
    y = df["target_21d"].values
    n = len(df)
    i_train = int(0.8*n)
    i_valid = int(0.9*n)
    X_tr, y_tr = X[:i_train], y[:i_train]
    X_va, y_va = X[i_train:i_valid], y[i_train:i_valid]
    X_te, y_te = X[i_valid:], y[i_valid:]

    model = GradientBoostingRegressor(
        n_estimators=cfg.get("n_estimators", 300),
        learning_rate=cfg.get("learning_rate", 0.05),
        max_depth=cfg.get("max_depth", 3),
        random_state=42
    )
    model.fit(X_tr, y_tr)
    # Avaliação
    pred_va = model.predict(X_va)
    pred_te = model.predict(X_te)
    rmse_va = float(np.sqrt(mean_squared_error(y_va, pred_va)))
    rmse_te = float(np.sqrt(mean_squared_error(y_te, pred_te)))
    ic_va = float(information_coefficient(y_va, pred_va))
    ic_te = float(information_coefficient(y_te, pred_te))

    # Para top-bottom, precisamos do cross-section por data.
    df_valid = df.iloc[i_train:i_valid].copy()
    df_valid["pred"] = pred_va
    spread_va = float(top_bottom_spread(df_valid, "pred", "target_21d", q=0.1))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feat_cols}, MODEL_PATH)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "rmse_valid": rmse_va,
            "rmse_test": rmse_te,
            "ic_valid": ic_va,
            "ic_test": ic_te,
            "top_bottom_spread_valid": spread_va,
            "n": n
        }, f, indent=2)
    print(f"[train] salvo: {MODEL_PATH} | metrics: {METRICS_PATH}")

if __name__ == "__main__":
    main()
