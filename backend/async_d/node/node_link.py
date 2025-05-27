import logging
from abc import ABC, abstractmethod
logger = logging.getLogger(__name__)


class NodeLink(ABC):
    @property
    def src_nodes_id(self):
        return ", ".join(
            [
                ".".join(map(str, node.serial_number)) + ": " + node.__name__
                for node in self.src_nodes.values()
            ]
        )

    @property
    def dst_node_id(self):
        return ", ".join(
            [
                ".".join(map(str, node.serial_number)) + ": " + node.__name__
                for node in self.dst_nodes.values()
            ]
        )

    @abstractmethod
    def set_src_node(self, node):
        pass
    
    @abstractmethod
    def set_dst_node(self, node):
        pass

    @abstractmethod
    def put(self, data):
        pass
    
    @abstractmethod
    def connect(self, node, criteria=lambda data: True):
        pass

    def __rshift__(self, other):
        self.connect(other)
        return other

