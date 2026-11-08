from __future__ import annotations

from typing import Iterator

from ._dlist import DList, Node
from .base import BaseCache


class LRUCache(BaseCache):
    """Least Recently Used: when full, evict the entry untouched the longest.

    Hash map  -> find any entry in O(1)
    Linked list -> keep entries ordered by recency, move/remove in O(1)

    >>> c = LRUCache(2)
    >>> c.put("a", 1); c.put("b", 2)
    >>> c.get("a")
    1
    >>> c.put("c", 3)      # "b" was used least recently, so it is evicted
    >>> "b" in c, "a" in c
    (False, True)
    """

    def __init__(self, capacity: int, **options) -> None:
        super().__init__(capacity, **options)
        self._list = DList()

    def _insert(self, node: Node) -> None:
        self._list.push_front(node)

    def _touch(self, node: Node) -> None:
        self._list.move_to_front(node)

    def _unlink(self, node: Node) -> None:
        self._list.remove(node)

    def _victim(self) -> Node:
        return self._list.back()

    def _reset(self) -> None:
        self._list = DList()

    def _order(self) -> Iterator[Node]:
        return iter(self._list)  # most recent -> least recent
