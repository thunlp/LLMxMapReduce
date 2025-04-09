import logging
from abc import ABC, abstractmethod

import gevent
from gevent import spawn
from ..node.abstract_node import AbstractNode

logger = logging.getLogger(__name__)


class NodeGroup(AbstractNode, ABC):
    def __init__(self, all_nodes):
        super().__init__()
        assert len(all_nodes) != 0, f"No node to compose the node group {self.__name__}"
        self.all_nodes = {node.__name__: node for node in all_nodes}
        self._connect_nodes()
        self._watch_nodes = gevent.spawn(self._watch_nodes)

    @abstractmethod
    def _connect_nodes(self):
        logger.error(
            f"Not implemented the self._connect_nodes method in {self.__name__}"
        )

    def _watch_nodes(self):
        while self.is_start:
            if all([not node.is_start for node in self.all_nodes.values()]):
                self.is_start = False
            gevent.sleep(5)

    def start(self):
        if self.serial_number is None:
            self.serial_number = [0]
        for i, node in enumerate(self.all_nodes.values()):
            node.set_serial_number(self.serial_number + [i])
            node.start()
        self.is_start = True
        return

    def end(self):
        heads = self._find_head_nodes()
        for head in heads:
            head.end()
        self._watch_nodes.join()
        self.is_start = False

    def _find_head_nodes(self):
        nodes = []
        for node in self.all_nodes.values():
            if any([src not in self.all_nodes.values() for src in node.src_nodes]):
                nodes.append(node)
        return nodes
