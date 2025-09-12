import logging
from abc import ABC, abstractmethod

import gevent
from .node_group import NodeGroup
from ..node.node_link import NodeLink
from ..node.abstract_node import AbstractNode

logger = logging.getLogger(__name__)


class Pipeline(NodeGroup, NodeLink):
    def __init__(self, all_nodes, head=None, tail=None):
        super().__init__(all_nodes=all_nodes)
        assert len(all_nodes) != 0, f"No node to compose the node group {self.__name__}"
        self.all_nodes = {node.__name__: node for node in all_nodes}
        self._connect_nodes()

        if head is None:
            self.head = all_nodes[0]
        else:
            self.head = head
        if tail is None:
            self.tail = all_nodes[-1]
        else:
            self.tail = tail

    @abstractmethod
    def _connect_nodes(self):
        logger.error(
            f"Not implemented the self._connect_nodes method in {self.__name__}"
        )

    @property
    def src_nodes(self):
        return self.head.src_nodes

    @src_nodes.setter
    def src_nodes(self, value):
        self.head.src_nodes = value

    def set_src_node(self, node):
        return self.head.set_src_node(node)

    @property
    def dst_nodes(self):
        return self.tail.dst_nodes

    @dst_nodes.setter
    def dst_nodes(self, value):
        self.tail.dst_nodes = value

    def set_dst_node(self, node):
        return self.tail.set_dst_node(node)

    def put(self, data):
        self.head.put(data)

    def connect(self, node, criteria=lambda data: True):
        self.tail.set_dst_node(node)
        node.set_src_node(self)
        self.set_dst_criteria(node, criteria)

    def set_dst_criteria(self, node, criteria):
        self.tail.set_dst_criteria(node, criteria)
