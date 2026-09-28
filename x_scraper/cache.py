"""SQLite response cache so repeated scrapes don't re-hit the network."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class Cache:
    def __init__(self, path: str | Path = "x_scraper_cache.sqlite3", ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, stored_at REAL NOT NULL)"
        )
        self._conn.commit()

    @staticmethod
    def key_for(endpoint: str, params: dict) -> str:
        raw = endpoint + json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT value, stored_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, stored_at = row
        if time.time() - stored_at > self.ttl_seconds:
            return None
        return json.loads(value)

    def set(self, key: str, value: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
