"""
Unit tests -- Query caching layer.
"""
import time
import pytest
from src.copilot.cache import QueryCache, get_cache


def test_put_and_get():
    cache = QueryCache(ttl=60)
    cache.put("revenue by country", "mock", True, {"result": "data"})
    result = cache.get("revenue by country", "mock", True)
    assert result == {"result": "data"}


def test_cache_miss():
    cache = QueryCache(ttl=60)
    result = cache.get("unknown question", "mock", True)
    assert result is None


def test_different_params_different_keys():
    cache = QueryCache(ttl=60)
    cache.put("revenue", "mock", True, "exec_true")
    cache.put("revenue", "mock", False, "exec_false")
    assert cache.get("revenue", "mock", True) == "exec_true"
    assert cache.get("revenue", "mock", False) == "exec_false"


def test_cache_expiry():
    cache = QueryCache(ttl=0.1)  # 100ms TTL
    cache.put("question", "mock", True, "value")
    time.sleep(0.15)
    assert cache.get("question", "mock", True) is None


def test_invalidate_specific():
    cache = QueryCache(ttl=60)
    cache.put("q1", "mock", True, "v1")
    cache.put("q2", "mock", True, "v2")
    removed = cache.invalidate("q1", "mock", True)
    assert removed == 1
    assert cache.get("q1", "mock", True) is None
    assert cache.get("q2", "mock", True) == "v2"


def test_invalidate_all():
    cache = QueryCache(ttl=60)
    cache.put("q1", "mock", True, "v1")
    cache.put("q2", "mock", True, "v2")
    removed = cache.invalidate()
    assert removed == 2
    assert cache.get("q1", "mock", True) is None
    assert cache.get("q2", "mock", True) is None


def test_max_size_eviction():
    cache = QueryCache(ttl=60, max_size=2)
    cache.put("q1", "mock", True, "v1")
    cache.put("q2", "mock", True, "v2")
    cache.put("q3", "mock", True, "v3")  # should evict q1
    assert cache.get("q1", "mock", True) is None
    assert cache.get("q3", "mock", True) == "v3"


def test_stats():
    cache = QueryCache(ttl=60)
    cache.put("q1", "mock", True, "v1")
    cache.get("q1", "mock", True)  # hit
    cache.get("q2", "mock", True)  # miss
    stats = cache.stats()
    assert stats["size"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5


def test_cleanup_expired():
    cache = QueryCache(ttl=0.1)
    cache.put("q1", "mock", True, "v1")
    cache.put("q2", "mock", True, "v2")
    time.sleep(0.15)
    removed = cache.cleanup_expired()
    assert removed == 2
    assert cache.stats()["size"] == 0


def test_case_insensitive_key():
    """Cache keys should be case-insensitive."""
    cache = QueryCache(ttl=60)
    cache.put("Revenue by Country", "mock", True, "result")
    assert cache.get("revenue by country", "mock", True) == "result"


def test_global_singleton():
    """get_cache() should return the same instance."""
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2


def test_hit_count_increments():
    cache = QueryCache(ttl=60)
    cache.put("q1", "mock", True, "v1")
    cache.get("q1", "mock", True)
    cache.get("q1", "mock", True)
    stats = cache.stats()
    assert stats["hits"] == 2
