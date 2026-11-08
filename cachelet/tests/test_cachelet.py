import random
import threading
from collections import OrderedDict

import pytest

from cachelet import CacheStats, LFUCache, LRUCache, cached


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


# ---------------- LRU ----------------
def test_lru_evicts_least_recently_used():
    c = LRUCache(2)
    c.put("a", 1); c.put("b", 2)
    c.get("a")
    c.put("c", 3)
    assert "b" not in c and "a" in c and "c" in c


def test_lru_update_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1); c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10 and "b" not in c


def test_lru_order_and_capacity_one():
    c = LRUCache(3)
    for k in "abc": c.put(k, k)
    c.get("a")
    assert c.keys() == ["a", "c", "b"]  # most -> least recent
    one = LRUCache(1)
    one.put("x", 1); one.put("y", 2)
    assert one.keys() == ["y"]


def test_peek_and_contains_do_not_refresh():
    c = LRUCache(2)
    c.put("a", 1); c.put("b", 2)
    assert c.peek("a") == 1 and "a" in c
    c.put("c", 3)
    assert "a" not in c  # a was still the oldest


def test_dict_sugar_and_missing():
    c = LRUCache(2)
    c["a"] = 1
    assert c["a"] == 1 and len(c) == 1
    with pytest.raises(KeyError):
        c["zzz"]
    del c["a"]
    with pytest.raises(KeyError):
        del c["a"]


def test_none_values_are_real_values():
    c = LRUCache(2)
    c.put("a", None)
    assert "a" in c and c["a"] is None


def test_delete_pop_clear():
    c = LRUCache(3)
    for k in "abc": c.put(k, k.upper())
    assert c.delete("a") and not c.delete("a")
    assert c.pop("b") == "B" and c.pop("b", "gone") == "gone"
    with pytest.raises(KeyError):
        c.pop("b")
    c.clear()
    assert len(c) == 0 and c.keys() == []
    c.put("z", 1)
    assert c.keys() == ["z"]


def test_stats_and_callback():
    evicted = []
    c = LRUCache(1, on_evict=lambda k, v: evicted.append((k, v)))
    c.put("a", 1); c.get("a"); c.get("nope"); c.put("b", 2)
    s = c.stats
    assert isinstance(s, CacheStats)
    assert (s.hits, s.misses, s.evictions, s.size, s.capacity) == (1, 1, 1, 1, 1)
    assert s.hit_rate == 0.5
    assert evicted == [("a", 1)]


def test_bad_arguments():
    for bad in (0, -1, 1.5):
        with pytest.raises(ValueError):
            LRUCache(bad)
    with pytest.raises(ValueError):
        LRUCache(2, ttl=0)


# ---------------- TTL ----------------
def test_ttl_expiry():
    clock = Clock()
    c = LRUCache(3, ttl=10, timer=clock)
    c.put("a", 1)
    clock.t = 9
    assert c.get("a") == 1
    clock.t = 10
    assert c.get("a") is None and "a" not in c
    assert c.stats.expirations == 1 and len(c) == 0


def test_ttl_put_resets_and_purge():
    clock = Clock()
    c = LRUCache(3, ttl=10, timer=clock)
    c.put("a", 1); c.put("b", 2)
    clock.t = 8
    c.put("a", 1)       # refreshes a's deadline
    clock.t = 12
    assert c.keys() == ["a"]
    assert c.purge() == 1 and len(c) == 1


# ---------------- LFU ----------------
def test_lfu_evicts_least_frequent():
    c = LFUCache(2)
    c.put("a", 1); c.put("b", 2)
    c.get("a"); c.get("a")
    c.put("c", 3)
    assert "b" not in c and "a" in c and c.frequency("a") == 3


def test_lfu_tie_broken_by_recency():
    c = LFUCache(2)
    c.put("a", 1); c.put("b", 2)   # both freq 1; a is older
    c.put("c", 3)
    assert "a" not in c and "b" in c


def test_lfu_new_item_can_be_evicted_next():
    c = LFUCache(2)
    c.put("a", 1); c.get("a")
    c.put("b", 2)
    c.put("c", 3)        # b (freq 1) goes, a (freq 2) stays
    assert c.keys() == ["a", "c"]


def test_lfu_delete_leaves_min_consistent():
    c = LFUCache(2)
    c.put("a", 1); c.put("b", 2); c.get("b"); c.get("b")
    c.delete("a")        # removes the only freq-1 entry
    c.put("c", 3); c.put("d", 4)
    assert "b" in c and len(c) == 2


# ---------------- decorator ----------------
def test_cached_decorator():
    calls = []

    @cached(maxsize=2)
    def sq(x, y=1):
        calls.append((x, y))
        return x * x + y

    assert sq(3) == 10 and sq(3) == 10 and sq(3, y=2) == 11
    assert len(calls) == 2
    info = sq.cache_info()
    assert info.hits == 1 and info.misses == 2
    sq.cache_clear()
    sq(3)
    assert len(calls) == 3


def test_cached_bare_and_none_result_and_lfu():
    n = {"calls": 0}

    @cached
    def f(x):
        n["calls"] += 1

    f(1); f(1)
    assert n["calls"] == 1  # None results are cached too

    @cached(policy="lfu", maxsize=1)
    def g(x): return x
    assert g(5) == 5
    with pytest.raises(ValueError):
        cached(policy="fifo")


# ---------------- model-based randomized tests ----------------
def test_lru_matches_ordereddict_model():
    rng = random.Random(1)
    cap, c, ref = 7, LRUCache(7), OrderedDict()
    for _ in range(5000):
        k, op = rng.randint(0, 15), rng.random()
        if op < 0.45:
            assert c.get(k) == ref.get(k)
            if k in ref: ref.move_to_end(k, last=False)
        elif op < 0.9:
            c.put(k, k * 2)
            ref[k] = k * 2; ref.move_to_end(k, last=False)
            if len(ref) > cap: ref.popitem(last=True)
        else:
            assert c.delete(k) == (ref.pop(k, None) is not None)
        assert c.keys() == list(ref)


def test_lfu_matches_bruteforce_model():
    rng = random.Random(2)
    cap, c, ref, tick = 6, LFUCache(6), {}, 0   # ref: key -> [freq, last_tick]
    for _ in range(6000):
        tick += 1
        k, op = rng.randint(0, 12), rng.random()
        if op < 0.45:
            assert (c.get(k) is not None) == (k in ref)
            if k in ref: ref[k][0] += 1; ref[k][1] = tick
        elif op < 0.9:
            c.put(k, 1)
            if k in ref: ref[k][0] += 1; ref[k][1] = tick
            else:
                if len(ref) >= cap:
                    del ref[min(ref, key=lambda x: tuple(ref[x]))]
                ref[k] = [1, tick]
        else:
            assert c.delete(k) == (ref.pop(k, None) is not None)
        assert set(c.keys()) == set(ref)


# ---------------- threads ----------------
@pytest.mark.parametrize("cls", [LRUCache, LFUCache])
def test_thread_safety(cls):
    c = cls(50, thread_safe=True)

    def work(seed):
        rng = random.Random(seed)
        for _ in range(8000):
            k = rng.randint(0, 120)
            if rng.random() < 0.5: c.put(k, k)
            else: c.get(k)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len(c) <= 50 and len(c) == len(c.keys())
