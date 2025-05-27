
from typing import List, Set

class MultiKeyDict:
    # multiple key could correspond to one value, used in multiple bibkey to find one digest
    def __init__(self):
        self._data = {}

    def add(self, keys: Set[str], value):
        self._data[frozenset(keys)] = value

    def get(self, key: str):
        for keys, digest in self._data.items():
            if key in keys:
                return digest
        return None

    def keys(self):
        return {key for keys in self._data.keys() for key in keys}

    def values(self):
        return self._data.values()

    def items(self):
        return [(keys, digest) for keys, digest in self._data.items()]

    def __setitem__(self, keys: Set[str], value):
        self.add(keys, value)

    def __getitem__(self, key: str):
        if isinstance(key, str):
            return self.get(key)
        elif isinstance(key, frozenset):
            return self._data[key]

    def __delitem__(self, key: str):
        for keys in list(self._data.keys()):
            if key in keys:
                del self._data[keys]
                break

    def __contains__(self, key: str):
        return any(key in keys for keys in self._data.keys())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self._data)

    def clear(self):
        self._data.clear()

    def update(self, *args, **kwargs):
        for keys, value in dict(*args, **kwargs).items():
            self.add(keys, value)

    def __repr__(self):
        return repr(self._data)

    def __str__(self):
        return str(self._data)