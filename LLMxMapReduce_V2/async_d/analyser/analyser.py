import logging
from .singleton_meta import SingletonMeta

logger = logging.getLogger(__name__)


class Analyser(metaclass=SingletonMeta):
    def __init__(self) -> None:
        pass

    def start(self):
        raise NotImplementedError("Subclasses should implement this method")

    def report(self) -> str:
        raise NotImplementedError("Subclasses should implement this method")
