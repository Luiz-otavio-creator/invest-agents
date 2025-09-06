# common/utils/io.py
import json, os
from typing import Any, Dict

def read_yaml_or_json(path: str) -> Dict[str, Any]:
    """Reads YAML if available, otherwise JSON. Falls back to JSON on parse error."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    # Try YAML
    try:
        import yaml  # type: ignore
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        # Fallback to JSON
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def read_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
