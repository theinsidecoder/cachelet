"""Shared machinery: hash map lookup, TTL, stats, locking, eviction callbacks.

A policy (LRU, LFU...) only has to answer four questions:
  _insert(node)  - a new entry arrived
  _touch(node)   - an entry was used
  _unlink(node)  - an entry left
  _victim()      - who should be evicted next?
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Iterator, List, Optional, Tuple

from ._dlist import Node

_MISSING = object()


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int
    expirations: int
    size: int
    capacity: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class BaseCache:
    def __init__(
        self,
        capacity: int,
        *,
        ttl: Optional[float] = None,
        on_evict: Optional[Callable[[Hashable, Any], None]] = None,
        thread_safe: bool = False,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        self._capacity = capacity
        self._ttl = ttl
        self._on_evict = on_evict
        self._timer = timer
        self._lock = threading.RLock() if thread_safe else contextlib.nullcontext()
        self._map: Dict[Hashable, Node] = {}
        self._hits = self._misses = self._evictions = self._expirations = 0

    # ----- policy hooks (implemented by subclasses) -----
    def _insert(self, node: Node) -> None: raise NotImplementedError
    def _touch(self, node: Node) -> None: raise NotImplementedError
    def _unlink(self, node: Node) -> None: raise NotImplementedError
    def _victim(self) -> Node: raise NotImplementedError
    def _reset(self) -> None: raise NotImplementedError
    def _order(self) -> Iterator[Node]: raise NotImplementedError

    # ----- internals -----
    def _expired(self, node: Node) -> bool:
        return node.expires is not None and self._timer() >= node.expires

    def _drop(self, node: Node) -> None:
        del self._map[node.key]
        self._unlink(node)

    def _live(self, key: Hashable) -> Optional[Node]:
        """Find a node; silently remove it if its TTL ran out."""
        node = self._map.get(key)
        if node is not None and self._expired(node):
            self._drop(node)
            self._expirations += 1
            return None
        return node

    # ----- public API -----
    @property
    def capacity(self) -> int:
        return self._capacity

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Look up a key. Counts as a use (and as a hit or miss)."""
        with self._lock:
            node = self._live(key)
            if node is None:
                self._misses += 1
                return default
            self._hits += 1
            self._touch(node)
            return node.value

    def put(self, key: Hashable, value: Any) -> None:
        """Insert or update. Evicts one entry first if the cache is full."""
        with self._lock:
            expires = self._timer() + self._ttl if self._ttl is not None else None
            node = self._live(key)
            if node is not None:
                node.value, node.expires = value, expires
                self._touch(node)
                return
            if len(self._map) >= self._capacity:
                victim = self._victim()
                self._drop(victim)
                self._evictions += 1
                if self._on_evict:
                    self._on_evict(victim.key, victim.value)
            node = Node(key, value)
            node.expires = expires
            self._map[key] = node
            self._insert(node)

    def peek(self, key: Hashable, default: Any = None) -> Any:
        """Read a value WITHOUT counting it as a use (no stats, no reordering)."""
        with self._lock:
            node = self._map.get(key)
            if node is None or self._expired(node):
                return default
            return node.value

    def delete(self, key: Hashable) -> bool:
        with self._lock:
            node = self._map.get(key)
            if node is None:
                return False
            self._drop(node)
            return True

    def pop(self, key: Hashable, default: Any = _MISSING) -> Any:
        with self._lock:
            node = self._live(key)
            if node is None:
                if default is _MISSING:
                    raise KeyError(key)
                return default
            self._drop(node)
            return node.value

    def purge(self) -> int:
        """Remove every expired entry. Returns how many were removed."""
        with self._lock:
            dead = [n for n in self._map.values() if self._expired(n)]
            for n in dead:
                self._drop(n)
            self._expirations += len(dead)
            return len(dead)

    def clear(self) -> None:
        with self._lock:
            self._map.clear()
            self._reset()

    def keys(self) -> List[Hashable]:
        with self._lock:
            return [n.key for n in self._order() if not self._expired(n)]

    def items(self) -> List[Tuple[Hashable, Any]]:
        with self._lock:
            return [(n.key, n.value) for n in self._order() if not self._expired(n)]

    @property
    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(self._hits, self._misses, self._evictions,
                              self._expirations, len(self._map), self._capacity)

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = self._misses = self._evictions = self._expirations = 0

    # ----- dict-like sugar -----
    def __getitem__(self, key: Hashable) -> Any:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __setitem__(self, key: Hashable, value: Any) -> None:
        self.put(key, value)

    def __delitem__(self, key: Hashable) -> None:
        if not self.delete(key):
            raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        with self._lock:
            node = self._map.get(key)  # type: ignore[arg-type]
            return node is not None and not self._expired(node)

    def __len__(self) -> int:
        return len(self._map)

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self.keys())

    def __repr__(self) -> str:
        return f"{type(self).__name__}(size={len(self._map)}, capacity={self._capacity})"
