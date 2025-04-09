from collections.abc import Iterable


class Dataset:
    def __init__(self, *args, **kwargs):
        self._data = []
        if len(args) == 1 and isinstance(args[0], Iterable):
            for data in args[0]:
                if isinstance(data, tuple):
                    self._data.append(data)
                else:
                    self._data.append((data,))
        else:
            self._data = [args]

    def __len__(self):
        return len(self._data)
    
    @property
    def size(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)