import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AbstractNode(ABC):
    def __init__(self):
        # different layer of nodes will have different serial number
        # inherited from the parent node group
        self.serial_number = []
        self.__name__ = self.__class__.__name__
        self.head = None
        self.tail = None
        self.is_start = False

    def set_name(self, name):
        self.__name__ = name

    def set_serial_number(self, serial_number):
        self.serial_number = serial_number

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def end(self):
        pass
