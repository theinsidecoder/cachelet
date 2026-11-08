from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from .base import BaseCache, _MISSING
from .lfu import LFUCache
from .lru import LRUCache


def _make_key(args: tuple, kwargs: dict) -> tuple:
    return args, tuple(sorted(kwargs.items()))


def cached(
    fn: Optional[Callable] = None,
    *,
    maxsize: int = 128,
    ttl: Optional[float] = None,
    policy: str = "lru",
    cache: Optional[BaseCache] = None,
):
    """Memoize a function with an LRU/LFU cache (optionally with a TTL).

        @cached(maxsize=256, ttl=60)
        def fetch(user_id): ...

        fetch.cache_info()   # hits, misses, ...
        fetch.cache_clear()
    """
    if policy not in ("lru", "lfu"):
        raise ValueError("policy must be 'lru' or 'lfu'")

    def decorate(func: Callable) -> Callable:
        store = cache if cache is not None else (LRUCache if policy == "lru" else LFUCache)(
            maxsize, ttl=ttl, thread_safe=True
        )

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_key(args, kwargs)
            value = store.get(key, _MISSING)
            if value is _MISSING:
                value = func(*args, **kwargs)
                store.put(key, value)
            return value

        wrapper.cache = store
        wrapper.cache_info = lambda: store.stats
        wrapper.cache_clear = store.clear
        return wrapper

    return decorate(fn) if callable(fn) else decorate
