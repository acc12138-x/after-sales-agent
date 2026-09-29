"""LLM 语义缓存：相同/相似问题直接返回。

后端可插拔：
- SQLite（默认，零依赖）
- Redis（高并发、分布式）

切换：.env 里设 CACHE_BACKEND=redis 或 sqlite
"""
from __future__ import annotations
import hashlib
import json
import os
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


def _hash(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()


def _emb_to_bytes(emb: List[float]) -> bytes:
    return np.array(emb, dtype=np.float32).tobytes()


def _bytes_to_emb(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ============================================================
# SQLite 后端
# ============================================================
class SqliteBackend:
    name = "sqlite"

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

    def get_exact(self, query: str) -> Optional[dict]:
        h = _hash(query)
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

    def get_semantic(self, query_embedding: List[float], threshold: float = SEMANTIC_THRESHOLD) -> Optional[dict]:
        q = np.array(query_embedding, dtype=np.float32)
        now = time.time()
        best = None
        best_sim = 0.0
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM cache_entries WHERE expires_at > ? AND embedding IS NOT NULL",
                (now,),
            ).fetchall()
            for row in rows:
                emb = _bytes_to_emb(row["embedding"])
                if emb.shape[0] != q.shape[0]:
                    continue
                sim = _cosine(q, emb)
                if sim > best_sim:
                    best_sim = sim
                    best = row
            if best is None or best_sim < threshold:
                return None
            c.execute("UPDATE cache_entries SET hit_count = hit_count + 1 WHERE id = ?", (best["id"],))
            c.commit()
        result = json.loads(best["response_json"])
        result["_cache_similarity"] = round(best_sim, 4)
        result["_cache_query"] = best["query"]
        return result

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
        h = _hash(query)
        now = time.time()
        emb_blob = _emb_to_bytes(embedding) if embedding is not None else None
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

    def clear_all(self) -> int:
        with self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            c.execute("DELETE FROM cache_entries")
            c.commit()
            return n

    def clear_expired(self) -> int:
        with self._conn() as c:
            n = c.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (time.time(),)).rowcount
            c.commit()
            return n

    def stats(self) -> dict:
        now = time.time()
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?", (now,)).fetchone()[0]
            hits = c.execute("SELECT SUM(hit_count) FROM cache_entries").fetchone()[0] or 0
            with_emb = c.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE embedding IS NOT NULL AND expires_at > ?",
                (now,),
            ).fetchone()[0]
        return {
            "backend": "sqlite",
            "active_entries": total,
            "total_hits": int(hits),
            "with_embedding": with_emb,
            "db_path": str(_DB_PATH),
        }


# ============================================================
# Redis 后端
# ============================================================
class RedisBackend:
    name = "redis"

    def __init__(self, url: str = "redis://127.0.0.1:6379/0"):
        import redis
        # Redis 5.x 不支持 RESP3，强制 protocol=2
        # 更老的 redis-py 可能没有 protocol 参数，做兼容
        try:
            self.client = redis.from_url(
                url, decode_responses=False, protocol=2,
                socket_connect_timeout=3, socket_timeout=3,
            )
        except TypeError:
            # 老版 redis-py 不支持 protocol 参数
            self.client = redis.from_url(
                url, decode_responses=False,
                socket_connect_timeout=3, socket_timeout=3,
            )
        # 测试连通
        self.client.ping()

    def _key(self, h: str) -> str:
        return f"cache:exact:{h}"

    def _sem_key(self) -> str:
        return "cache:semantic:index"    # 存 hash 列表

    def get_exact(self, query: str) -> Optional[dict]:
        h = _hash(query)
        raw = self.client.get(self._key(h))
        if raw is None:
            return None
        self.client.hincrby(f"cache:hits:{h}", "count", 1)
        return json.loads(raw)

    def get_semantic(self, query_embedding: List[float], threshold: float = SEMANTIC_THRESHOLD) -> Optional[dict]:
        q = np.array(query_embedding, dtype=np.float32)
        # 遍历所有 semantic key
        keys = self.client.smembers(self._sem_key())
        best_hash = None
        best_sim = 0.0
        for k in keys:
            k = k.decode() if isinstance(k, bytes) else k
            emb_raw = self.client.get(f"cache:emb:{k}")
            if not emb_raw:
                continue
            emb = _bytes_to_emb(emb_raw)
            if emb.shape[0] != q.shape[0]:
                continue
            sim = _cosine(q, emb)
            if sim > best_sim:
                best_sim = sim
                best_hash = k
        if best_hash is None or best_sim < threshold:
            return None
        raw = self.client.get(self._key(best_hash))
        if raw is None:
            return None
        self.client.hincrby(f"cache:hits:{best_hash}", "count", 1)
        result = json.loads(raw)
        # 补 query
        qtext = self.client.get(f"cache:q:{best_hash}")
        if qtext:
            result["_cache_query"] = qtext.decode() if isinstance(qtext, bytes) else qtext
        result["_cache_similarity"] = round(best_sim, 4)
        return result

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
        h = _hash(query)
        data = json.dumps(clean, ensure_ascii=False).encode("utf-8")
        self.client.setex(self._key(h), DEFAULT_TTL, data)
        self.client.setex(f"cache:q:{h}", DEFAULT_TTL, query.encode("utf-8"))
        if embedding is not None:
            self.client.setex(f"cache:emb:{h}", DEFAULT_TTL, _emb_to_bytes(embedding))
            self.client.sadd(self._sem_key(), h)

    def clear_all(self) -> int:
        # 只清本项目命名的 key
        n = 0
        for pattern in ["cache:exact:*", "cache:semantic:*", "cache:emb:*", "cache:q:*", "cache:hits:*"]:
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                n += self.client.delete(*keys)
        return n

    def clear_expired(self) -> int:
        # Redis 自动 TTL，无需手动
        return 0

    def stats(self) -> dict:
        exact_keys = list(self.client.scan_iter(match="cache:exact:*", count=100))
        sem_keys = list(self.client.scan_iter(match="cache:emb:*", count=100))
        # 汇总 hits
        total_hits = 0
        for k in self.client.scan_iter(match="cache:hits:*", count=100):
            v = self.client.hget(k, "count")
            if v:
                total_hits += int(v)
        return {
            "backend": "redis",
            "active_entries": len(exact_keys),
            "total_hits": total_hits,
            "with_embedding": len(sem_keys),
            "redis_url": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        }


# ============================================================
# 工厂
# ============================================================
_service = None


def _pick_backend():
    """选择后端：优先 settings，其次 os.environ，最后 sqlite。"""
    backend = "sqlite"
    url = "redis://127.0.0.1:6379/0"

    # 1. 优先从 settings 读（pydantic 会读 .env）
    try:
        from app.config.settings import get_settings
        s = get_settings()
        backend = (getattr(s, "cache_backend", "") or "sqlite").lower()
        url = getattr(s, "redis_url", url) or url
    except Exception:
        pass

    # 2. 环境变量覆盖（调试用）
    backend = (os.environ.get("CACHE_BACKEND") or backend).lower()
    url = os.environ.get("REDIS_URL") or url

    print(f"[CACHE] backend={backend} url={url}")

    if backend == "redis":
        try:
            return RedisBackend(url)
        except Exception as e:
            print(f"[CACHE] Redis 不可用，降级 SQLite：{e}")
            return SqliteBackend()
    return SqliteBackend()


def get_cache():
    global _service
    if _service is None:
        _service = _pick_backend()
    return _service


def reset_cache() -> None:
    global _service
    _service = None


# 保持旧接口
def get_exact(query: str) -> Optional[dict]:
    return get_cache().get_exact(query)


def get_semantic(emb, threshold=SEMANTIC_THRESHOLD):
    return get_cache().get_semantic(emb, threshold)


def clear_all() -> int:
    return get_cache().clear_all()
