"""
Query caching layer.

Provides a simple in-memory TTL cache for copilot query results.
Caches are keyed by (question, mode, execute) to avoid redundant
LLM calls, SQL generation, and database round-trips for frequently
asked questions.

The cache is process-local (dict-based) with configurable TTL and
max size.  For production multi-process deployments swap the backend
for Redis / Memcached.
"""
from __future__ import annotations

import hashlib
import time
import threading
from dataclasses import dataclass, field
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Configuration ───────────────────────────────────────

DEFAULT_TTL_SECONDS = 300  # 5 minutes
DEFAULT_MAX_SIZE = 256


# ── Cache entry ─────────────────────────────────────────


@dataclass
class CacheEntry:
    """A single cached result."""
    key: str
    value: Any
    created_at: float
    ttl: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


# ── Cache implementation ────────────────────────────────


class QueryCache:
    """Thread-safe in-memory TTL cache for copilot results.

    Parameters
    ----------
    ttl : float
        Time-to-live in seconds for each entry.
    max_size : int
        Maximum number of entries. Oldest entries are evicted when full.
    """

    def __init__(self, ttl: float = DEFAULT_TTL_SECONDS, max_size: int = DEFAULT_MAX_SIZE):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._ttl = ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    # ── Public API ──────────────────────────────────────

    def get(self, question: str, mode: str, execute: bool) -> Any | None:
        """Retrieve a cached result, or ``None`` on miss / expiry."""
        key = self._make_key(question, mode, execute)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._store[key]
                self._misses += 1
                return None
            entry.hit_count += 1
            self._hits += 1
            logger.debug("Cache HIT key=%s hits=%d", key[:16], entry.hit_count)
            return entry.value

    def put(self, question: str, mode: str, execute: bool, value: Any) -> None:
        """Store a result in the cache."""
        key = self._make_key(question, mode, execute)
        with self._lock:
            # Evict oldest if at capacity
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_oldest()
            self._store[key] = CacheEntry(
                key=key, value=value, created_at=time.time(), ttl=self._ttl,
            )
        logger.debug("Cache PUT key=%s size=%d", key[:16], len(self._store))

    def invalidate(self, question: str | None = None, mode: str = "mock", execute: bool = True) -> int:
        """Remove specific entry or flush all. Returns number of entries removed."""
        with self._lock:
            if question is None:
                count = len(self._store)
                self._store.clear()
                return count
            key = self._make_key(question, mode, execute)
            if key in self._store:
                del self._store[key]
                return 1
            return 0

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }

    # ── Internals ───────────────────────────────────────

    @staticmethod
    def _make_key(question: str, mode: str, execute: bool) -> str:
        """Deterministic cache key from inputs."""
        raw = f"{question.strip().lower()}|{mode}|{execute}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _evict_oldest(self) -> None:
        """Remove the entry with the earliest creation time."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
        del self._store[oldest_key]

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)


# ── Module-level singleton ──────────────────────────────

_cache = QueryCache()


def get_cache() -> QueryCache:
    """Return the global cache instance."""
    return _cache
