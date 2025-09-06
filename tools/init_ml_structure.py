# tools/init_ml_structure.py
# Cria a estrutura base de ML (pastas, __init__.py e esqueletos comentados)
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRS = [
    "features",
    "ml/datasets",
    "ml/trainers",
    "ml/models",
    "ml/utils",
    "config/ml",
]

FILES = {
    "features/__init__.py": """# features package
""",
    "features/base_features.py": r'''"""
features/base_features.py
-------------------------
Esqueleto de extração/transformação de fatores para equities.

✅ Objetivo (MVP):
- Funções para montar um "feature row" por (date, ticker).
- Semântica clara: cada função recebe DataFrames/series já coletados e retorna colunas novas.
- Sem look-ahead: use SOMENTE informações <= data de referência.

OBS: Aqui deixamos funções "stub" para você popular gradualmente.
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

def winsorize(s: pd.Series, p_low: float = 0.05, p_high: float = 0.95) -> pd.Series:
    lo, hi = s.quantile(p_low), s.quantile(p_high)
    return s.clip(lo, hi)

def zscore(s: pd.Series) -> pd.Series:
    mu, sd = s.mean(), s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd

def simple_tech_features(prices: pd.Series) -> Dict[str, float]:
    """
    prices: Series indexada por data com preços de fechamento ajustados (<= t)
    Retorna algumas features técnicas simples no último ponto (t):
    """
    s = prices.dropna()
    if s.empty:
        return {
            "ret_21d": np.nan,
            "ret_63d": np.nan,
            "vol_21d": np.nan,
            "sma_20_gap": np.nan,
            "sma_50_gap": np.nan,
            "sma_200_gap": np.nan,
            "rsi_14": np.nan,
        }
    # retornos
    ret_21d = (s.iloc[-1] / s.iloc[-21] - 1.0) if len(s) >= 22 else np.nan
    ret_63d = (s.iloc[-1] / s.iloc[-63] - 1.0) if len(s) >= 64 else np.nan
    # vol EWMA aproximada (21d)
    vol_21d = s.pct_change().ewm(span=21, adjust=False).std().iloc[-1] if len(s) > 21 else np.nan
    # SMAs
    sma20 = s.rolling(20).mean().iloc[-1] if len(s) >= 20 else np.nan
    sma50 = s.rolling(50).mean().iloc[-1] if len(s) >= 50 else np.nan
    sma200 = s.rolling(200).mean().iloc[-1] if len(s) >= 200 else np.nan
    px = s.iloc[-1]
    # gaps
    sma_20_gap = (px / sma20 - 1.0) if pd.notna(sma20) and sma20 > 0 else np.nan
    sma_50_gap = (px / sma50 - 1.0) if pd.notna(sma50) and sma50 > 0 else np.nan
    sma_200_gap = (px / sma200 - 1.0) if pd.notna(sma200) and sma200 > 0 else np.nan
    # RSI(14) simplificado
    r = s.diff().dropna()
    up = r.clip(lower=0.0).rolling(14).mean()
    dn = (-r.clip(upper=0.0)).rolling(14).mean()
    rs = (up / dn).iloc[-1] if len(up) >= 14 and len(dn) >= 14 and dn.iloc[-1] > 0 else np.nan
    rsi_14 = 100 - (100 / (1 + rs)) if pd.notna(rs) else np.nan

    return {
        "ret_21d": ret_21d,
        "ret_63d": ret_63d,
        "vol_21d": vol_21d,
        "sma_20_gap": sma_20_gap,
        "sma_50_gap": sma_50_gap,
        "sma_200_gap": sma_200_gap,
        "rsi_14": rsi_14,
    }

def merge_feature_blocks(blocks: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Mescla dicionários de features, prefixando com nome do bloco se desejado."""
    out: Dict[str, float] = {}
    for prefix, d in blocks.items():
        for k, v in d.items():
            key = f"{prefix}__{k}" if prefix else k
            out[key] = v
    return out
''',

    "ml/__init__.py": """# ml package
""",
    "ml/utils/__init__.py": """# ml.utils
""",
    "ml/utils/seeds.py": r'''"""
ml/utils/seeds.py
-----------------
Utilitário para reprodutibilidade.
"""
import os
import random
import numpy as np

def fix_seeds(seed: int = 42):
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
''',
    "ml/utils/splits.py": r'''"""
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
''',
    "ml/utils/metrics.py": r'''"""
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
''',

    "ml/datasets/__init__.py": """# ml.datasets
""",
    "ml/datasets/targets.py": r'''"""
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
''',
    "ml/datasets/build_equities.py": r'''"""
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
''',

    "ml/trainers/__init__.py": """# ml.trainers
""",
    "ml/trainers/equities_ranker.py": r'''"""
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
''',

    "config/ml/equities_ranker.yaml": r'''# config/ml/equities_ranker.yaml
# Hiperparâmetros do baseline (sklearn GradientBoostingRegressor)
n_estimators: 400
learning_rate: 0.05
max_depth: 3
''',
}

def ensure_dirs():
    for d in DIRS:
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)

def write_file(rel_path: str, content: str):
    p = ROOT / rel_path
    if p.exists():
        # não sobrescrever automaticamente; apenas avisa
        print(f"skip (existe): {rel_path}")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"created: {rel_path}")

def main():
    ensure_dirs()
    for rel, content in FILES.items():
        write_file(rel, content)
    print("\n✅ Estrutura ML criada. Próximos passos:")
    print("1) python -m ml.datasets.build_equities")
    print("2) python -m ml.trainers.equities_ranker")

if __name__ == "__main__":
    main()
