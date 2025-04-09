import hashlib


class LabelData:
    def __init__(self, data, label):
        self.data = data
        self.label = label


def generate_label(data):
    return hashlib.md5(str(data).encode("utf-8")).hexdigest()
