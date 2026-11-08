"""1) speed: cachelet LRU vs an O(n) list-based LRU vs OrderedDict
   2) quality: LRU vs LFU hit rate on a skewed workload with scans."""
import random
import time
from collections import OrderedDict

from cachelet import LFUCache, LRUCache


class ListLRU:                        # the "obvious" way: O(n) per access
    def __init__(self, cap): self.cap, self.d, self.order = cap, {}, []
    def get(self, k):
        if k in self.d:
            self.order.remove(k); self.order.append(k); return self.d[k]
    def put(self, k, v):
        if k in self.d: self.order.remove(k)
        elif len(self.d) >= self.cap: del self.d[self.order.pop(0)]
        self.d[k] = v; self.order.append(k)


class ODLRU:                          # strong baseline built on OrderedDict
    def __init__(self, cap): self.cap, self.d = cap, OrderedDict()
    def get(self, k):
        if k in self.d: self.d.move_to_end(k); return self.d[k]
    def put(self, k, v):
        if k in self.d: self.d.move_to_end(k)
        elif len(self.d) >= self.cap: self.d.popitem(last=False)
        self.d[k] = v


def ops_per_sec(make, cap, n=30_000):
    rng = random.Random(0)
    keys = [rng.randrange(cap * 2) for _ in range(n)]
    c = make(cap)
    t = time.perf_counter()
    for k in keys:
        if c.get(k) is None:
            c.put(k, k)
    return n / (time.perf_counter() - t)


print("Throughput (million ops/s, higher is better)\n")
print(f"{'capacity':>9}{'list LRU (O(n))':>18}{'OrderedDict':>14}{'cachelet LRU':>15}")
for cap in (100, 1_000, 5_000):
    a, b, c = (ops_per_sec(m, cap) / 1e6 for m in (ListLRU, ODLRU, LRUCache))
    print(f"{cap:>9}{a:>18.2f}{b:>14.2f}{c:>15.2f}")

# ---- hit rate: hot keys (Zipf-like) + occasional one-off scans ----
def workload(n=200_000, seed=3):
    rng = random.Random(seed)
    hot = list(range(200))
    weights = [1 / (i + 1) for i in range(len(hot))]
    scan_id = 10_000
    out = []
    while len(out) < n:
        if rng.random() < 0.002:                      # a scan: 300 never-repeated keys
            out.extend(range(scan_id, scan_id + 300)); scan_id += 300
        else:
            out.append(rng.choices(hot, weights)[0])
    return out[:n]


def hit_rate(cache, keys):
    for k in keys:
        if cache.get(k) is None:
            cache.put(k, k)
    return cache.stats.hit_rate

keys = workload()
print("\nHit rate on a skewed workload with periodic scans (capacity 100)\n")
print(f"  LRU: {hit_rate(LRUCache(100), keys):.1%}")
print(f"  LFU: {hit_rate(LFUCache(100), keys):.1%}")
