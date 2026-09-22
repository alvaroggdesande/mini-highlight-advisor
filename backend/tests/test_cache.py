from backend.cache import LRU


def test_get_miss_returns_none():
    assert LRU().get("nope") is None


def test_set_get_roundtrip():
    c = LRU()
    c.set("a", 1)
    assert c.get("a") == 1


def test_evicts_least_recently_used():
    c = LRU(maxsize=2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")  # 'a' now most-recent; 'b' is LRU
    c.set("c", 3)  # evicts 'b'
    assert c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3
