"""
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
