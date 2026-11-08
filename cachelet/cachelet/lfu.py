from __future__ import annotations

from typing import Dict, Hashable, Iterator

from ._dlist import DList, Node
from .base import BaseCache


class LFUCache(BaseCache):
    """Least Frequently Used: when full, evict the entry used the fewest times.
    Ties are broken by recency (the one untouched longest goes first).

    O(1) design: one linked list ("bucket") per use-count, plus `_min`,
    the smallest count that currently has entries.

        freq 1:  [d] <-> [e]
        freq 3:  [a]
        freq 7:  [b] <-> [c]        evict -> tail of the lowest bucket

    >>> c = LFUCache(2)
    >>> c.put("a", 1); c.put("b", 2)
    >>> c.get("a"); c.get("a")
    1
    1
    >>> c.put("c", 3)      # "b" was used least often, so it is evicted
    >>> "b" in c, "a" in c
    (False, True)
    """

    def __init__(self, capacity: int, **options) -> None:
        super().__init__(capacity, **options)
        self._buckets: Dict[int, DList] = {}
        self._min = 0

    def _bucket(self, freq: int) -> DList:
        b = self._buckets.get(freq)
        if b is None:
            b = self._buckets[freq] = DList()
        return b

    def _insert(self, node: Node) -> None:
        node.freq = 1
        self._bucket(1).push_front(node)
        self._min = 1

    def _touch(self, node: Node) -> None:
        f = node.freq
        bucket = self._buckets[f]
        bucket.remove(node)
        if not bucket:
            del self._buckets[f]
            if self._min == f:
                self._min = f + 1
        node.freq = f + 1
        self._bucket(f + 1).push_front(node)

    def _unlink(self, node: Node) -> None:
        bucket = self._buckets[node.freq]
        bucket.remove(node)
        if not bucket:
            del self._buckets[node.freq]

    def _victim(self) -> Node:
        if self._min not in self._buckets:  # can go stale after a delete
            self._min = min(self._buckets)
        return self._buckets[self._min].back()

    def _reset(self) -> None:
        self._buckets.clear()
        self._min = 0

    def _order(self) -> Iterator[Node]:
        for f in sorted(self._buckets, reverse=True):  # most used first
            yield from self._buckets[f]

    def frequency(self, key: Hashable) -> int:
        """How many times a key has been used (0 if absent). Does not count as a use."""
        node = self._map.get(key)
        return node.freq if node is not None else 0
