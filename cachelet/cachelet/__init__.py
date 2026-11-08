"""cachelet: tiny, dependency-free LRU and LFU caches with O(1) operations."""

from .base import CacheStats
from .decorator import cached
from .lfu import LFUCache
from .lru import LRUCache

__all__ = ["LRUCache", "LFUCache", "CacheStats", "cached"]
__version__ = "0.1.0"
