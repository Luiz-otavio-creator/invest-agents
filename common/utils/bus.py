# common/utils/bus.py
# Barramento simples baseado em arquivos (MVP).
import os, json, time
from typing import Any

def publish(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def subscribe(path: str, retries: int = 30, delay_s: float = 0.2):
    # Espera arquivo aparecer (simula pub/sub).
    for _ in range(retries):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        time.sleep(delay_s)
    raise TimeoutError(f"Timeout esperando {path}")
