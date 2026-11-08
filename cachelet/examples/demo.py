from cachelet import LFUCache, LRUCache, cached

# --- LRU: forgets what you haven't touched lately
lru = LRUCache(3)
for k in "abc":
    lru.put(k, k.upper())
lru.get("a")            # a is now the freshest
lru.put("d", "D")       # evicts b (least recently used)
print("LRU keys (fresh -> stale):", lru.keys())   # ['d', 'a', 'c']

# --- LFU: forgets what you rarely use
lfu = LFUCache(3)
for k in "abc":
    lfu.put(k, k.upper())
for _ in range(5):
    lfu.get("a")        # a is popular
lfu.get("b")
lfu.put("d", "D")       # evicts c (used the fewest times)
print("LFU keys (popular -> rare):", lfu.keys())  # ['a', 'b', 'd']

# --- TTL: entries expire on their own
short = LRUCache(10, ttl=0.05)
short.put("token", "abc123")
import time; time.sleep(0.06)
print("after ttl:", short.get("token"))           # None

# --- decorator
@cached(maxsize=100, ttl=60)
def slow_square(n):
    time.sleep(0.2)
    return n * n

slow_square(9); slow_square(9)                    # second call is instant
print(slow_square.cache_info())
