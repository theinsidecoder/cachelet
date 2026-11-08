"""A doubly linked list with sentinel nodes: O(1) insert, remove and move."""

from __future__ import annotations

from typing import Any, Iterator, Optional


class Node:
    __slots__ = ("key", "value", "prev", "next", "freq", "expires")

    def __init__(self, key: Any = None, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None
        self.freq = 0
        self.expires: Optional[float] = None


class DList:
    """Front = most recently used, back = least recently used."""

    __slots__ = ("head", "tail", "size")

    def __init__(self) -> None:
        self.head, self.tail = Node(), Node()  # sentinels: no edge-case `if`s needed
        self.head.next, self.tail.prev = self.tail, self.head
        self.size = 0

    def push_front(self, node: Node) -> None:
        node.prev, node.next = self.head, self.head.next
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node: Node) -> None:
        node.prev.next, node.next.prev = node.next, node.prev
        node.prev = node.next = None
        self.size -= 1

    def move_to_front(self, node: Node) -> None:
        if self.head.next is not node:
            self.remove(node)
            self.push_front(node)

    def back(self) -> Optional[Node]:
        return self.tail.prev if self.size else None

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[Node]:
        node = self.head.next
        while node is not self.tail:
            yield node
            node = node.next
