# common/cache/cache.py
import json, os, time
from typing import Any, Optional
from common.config.settings import SETTINGS

class FileCache:
    def __init__(self, path="out/cache.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, db):
        # 👇 AQUI: default=str evita erro com Timestamp/Decimal etc.
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, default=str)

    def get(self, key: str) -> Optional[Any]:
        db = self._load()
        item = db.get(key)
        if not item:
            return None
        if item["exp"] < time.time():
            del db[key]
            self._save(db)
            return None
        return item["val"]

    def set(self, key: str, value: Any, ttl: int):
        db = self._load()
        db[key] = {"exp": time.time() + ttl, "val": value}
        self._save(db)

_cache = FileCache()
def get_cache() -> FileCache:
    return _cache
