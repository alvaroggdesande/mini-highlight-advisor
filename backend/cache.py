from collections import OrderedDict


class LRU:
    def __init__(self, maxsize: int = 8):
        self._d: OrderedDict = OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def set(self, key, value) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)
