"""LLM 语义缓存：相同/相似问题直接返回。

设计：
- 后端可插拔：SQLite（默认，零依赖）
- 缓存粒度：query -> response（answer + intent + citations）
- 只缓存 qa 类意图（业务动作不缓存）
- 命中判定：精确 hash 或 embedding 余弦相似度 > 阈值
- 失效：知识库 ingest 时清空 + TTL 24h
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

_DB_PATH = Path("./data/cache.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CACHEABLE_INTENTS = {"qa"}
SEMANTIC_THRESHOLD = 0.90
DEFAULT_TTL = 86400  # 24h


class CacheService:
    def __init__(self):
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE,
                    query TEXT,
                    intent TEXT,
                    response_json TEXT,
                    embedding BLOB,
                    created_at REAL,
                    expires_at REAL,
                    hit_count INTEGER DEFAULT 0
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)")
            c.commit()

    def _hash(self, query: str) -> str:
        return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()

    def get_exact(self, query: str) -> Optional[dict]:
        h = self._hash(query)
        now = time.time()
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM cache_entries WHERE query_hash = ? AND expires_at > ?",
                (h, now),
            ).fetchone()
            if row is None:
                return None
            c.execute("UPDATE cache_entries SET hit_count = hit_count + 1 WHERE id = ?", (row["id"],))
            c.commit()
            return json.loads(row["response_json"])

    def set(self, query: str, response: dict, intent: str = "qa",
            embedding: Optional[List[float]] = None) -> None:
        if intent not in CACHEABLE_INTENTS:
            return
        clean = {
            "answer": response.get("answer"),
            "intent": intent,
            "confidence": response.get("confidence", 0.0),
            "citations": response.get("citations", []),
        }
        h = self._hash(query)
        now = time.time()
        emb_blob = None
        if embedding is not None:
            arr = np.array(embedding, dtype=np.float32)
            emb_blob = arr.tobytes()
        with self._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO cache_entries
                (query_hash, query, intent, response_json, embedding,
                 created_at, expires_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT hit_count FROM cache_entries WHERE query_hash = ?), 0))
            """, (h, query, intent,
                  json.dumps(clean, ensure_ascii=False),
                  emb_blob, now, now + DEFAULT_TTL, h))
            c.commit()

    def get_semantic(self, query_embedding: List[float],
                     threshold: float = SEMANTIC_THRESHOLD) -> Optional[dict]:
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0:
            return None

        now = time.time()
        best = None
        best_sim = 0.0
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM cache_entries WHERE expires_at > ? AND embedding IS NOT NULL",
                (now,),
            ).fetchall()

        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            if emb.shape[0] != q.shape[0]:
                continue
            e_norm = float(np.linalg.norm(emb))
            if e_norm == 0:
                continue
            sim = float(np.dot(q, emb) / (q_norm * e_norm))
            if sim > best_sim:
                best_sim = sim
                best = row

        if best is None or best_sim < threshold:
            return None

        with self._conn() as c:
            c.execute("UPDATE cache_entries SET hit_count = hit_count + 1 WHERE id = ?",
                      (best["id"],))
            c.commit()

        result = json.loads(best["response_json"])
        result["_cache_similarity"] = round(best_sim, 4)
        result["_cache_query"] = best["query"]
        return result

    def get_by_embedding(self, query: str, embedding: Optional[List[float]]) -> Optional[dict]:
        exact = self.get_exact(query)
        if exact:
            exact["_cache_hit"] = "exact"
            return exact
        if embedding is None:
            return None
        semantic = self.get_semantic(embedding)
        if semantic:
            semantic["_cache_hit"] = "semantic"
            return semantic
        return None

    def clear_all(self) -> int:
        with self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            c.execute("DELETE FROM cache_entries")
            c.commit()
            return n

    def clear_expired(self) -> int:
        with self._conn() as c:
            n = c.execute("DELETE FROM cache_entries WHERE expires_at <= ?",
                          (time.time(),)).rowcount
            c.commit()
            return n

    def stats(self) -> dict:
        now = time.time()
        with self._conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            hits = c.execute("SELECT SUM(hit_count) FROM cache_entries").fetchone()[0] or 0
            with_emb = c.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE embedding IS NOT NULL AND expires_at > ?",
                (now,),
            ).fetchone()[0]
        return {
            "active_entries": total,
            "total_hits": int(hits),
            "with_embedding": with_emb,
            "db_path": str(_DB_PATH),
        }


_service: Optional[CacheService] = None


def get_cache() -> CacheService:
    global _service
    if _service is None:
        _service = CacheService()
    return _service


def reset_cache() -> None:
    global _service
    _service = None
