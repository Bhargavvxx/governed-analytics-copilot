"""
Small shared utilities.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timer() -> Generator[dict, None, None]:
    """Context manager that records elapsed wall-clock milliseconds."""
    result: dict = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed_ms"] = int((time.perf_counter() - start) * 1000)
