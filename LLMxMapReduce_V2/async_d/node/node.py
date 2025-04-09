import logging
import traceback
import functools
from typing import Iterable

import gevent
import copy
from gevent import sleep, spawn
from gevent.queue import Queue
from tenacity import (
    retry,
    retry_if_not_exception_type,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .decorator import *

from .. import ASYNC_D_CONFIG
from ..exceptions import NodeProcessingError, NodeStop
from .abstract_node import AbstractNode
from .node_link import NodeLink

logger = logging.getLogger(__name__)
DEBUG_MOD = ASYNC_D_CONFIG.get("debug_mode", False)


class Node(AbstractNode, NodeLink):
    def __init__(
        self,
        proc_func,
        worker_num=None,
        queue_size=None,
        no_input=False,
        is_data_iterable=False,
        no_output=False,
        discard_none_output=False,
        skip_error=True,
        timeout=None,
        put_deepcopy_data=False
    ) -> None:
        super().__init__()
        self.timeout = timeout if timeout else ASYNC_D_CONFIG.get("timeout", None)
        self.worker_num = (
            worker_num if worker_num else ASYNC_D_CONFIG.get("worker_num", 1)
        )
        self.queue_size = (
            queue_size if queue_size else ASYNC_D_CONFIG.get("queue_size", 1)
        )

        self.__name__ = proc_func.__name__
        self.head = self
        self.tail = self
        self.is_start = False

        self.src_queue = Queue(self.queue_size)
        self.criterias = {}
        self.src_nodes = {}
        self.dst_nodes = {}
        self.get_data_lock = gevent.lock.Semaphore(1)

        self.no_input = no_input
        self.no_output = no_output
        self.is_data_iterable = is_data_iterable
        self.discard_none_output = discard_none_output
        self.skip_error = skip_error
        self.put_deepcopy_data = put_deepcopy_data
        
        # first decorator will first wrap, as the inner decorator
        self.get_decorators = []
        self.proc_decorators = []
        self.put_decorators = []
        self._proc_data = self._error_decorator(proc_func)

        self.tasks = []  # store all worker tasks
        self.executing_data_queue = []

    def start(self):
        """
        Starts the node's processing loop.
        """
        self._validate_destinations()
        self._setup_decorators()
        self._spawn_workers()
        self.is_start = True
        logger.info(
            f"Node {self.__name__} start, src_nodes: {self.src_nodes}, dst_nodes: {self.dst_nodes}"
        )
        return self.tasks

    def end(self):
        """
        Signals the end of the pipeline by putting a stop flag in the source queue.
        """
        for _ in range(self.worker_num):
            self.src_queue.put(NodeStop())

    def put(self, data):
        self.src_queue.put(data)

    def connect(self, node, criteria=None):
        self.set_dst_node(node)
        node.set_src_node(self)

        if criteria:
            self.set_dst_criteria(node, criteria)
        return node

    def set_dst_criteria(self, node, criteria):
        self.criterias[node.__name__] = criteria

    def set_dst_node(self, node):
        self.dst_nodes[node.__name__] = node

    def set_src_node(self, node):
        self.src_nodes[node.__name__] = node

    def add_proc_decorator(self, decorator):
        self.proc_decorators.append(decorator)

    def add_get_decorator(self, decorator):
        self.get_decorators.append(decorator)

    def add_put_decorator(self, decorator):
        self.put_decorators.append(decorator)

    def _validate_destinations(self):
        if self.no_output:
            assert (
                len(self.dst_nodes) == 0
            ), f"Node {self.__name__} has output queues, but set as no_output"
        else:
            assert len(self.dst_nodes) > 0, f"Node {self.__name__} dst_node is empty"

    def _setup_decorators(self):
        if self.skip_error:
            self.add_proc_decorator(skip_data_decorator)
        self._rearrange_proc_decorator()
        for decorator in self.get_decorators:
            self._get_one_data = decorator(self._get_one_data)
        for decorator in self.proc_decorators:
            self._proc_data = decorator(self._proc_data)
        for decorator in self.put_decorators:
            self._put_data = decorator(self._put_data)

    def _rearrange_proc_decorator(self):
        new_decorators = []

        def set_bottom_decorator(decorator):
            # former decorator in the inner layer
            if decorator in self.proc_decorators:
                new_decorators.append(decorator)
                self.proc_decorators.remove(decorator)

        def set_top_decorator(decorator):
            # latter decorator in the outer layer
            if decorator in self.proc_decorators:
                new_decorators.remove(decorator)
                new_decorators.append(decorator)

        for decorator in self.proc_decorators:
            new_decorators.append(decorator)

        set_top_decorator(label_proc_decorator)
        set_top_decorator(skip_data_decorator)

        self.proc_decorators = new_decorators

    def _spawn_workers(self):
        for i in range(self.worker_num):
            task = spawn(self._func_wrapper, i)
            self.tasks.append(task)

        self.get_data_generator = self._get_data()
        self.is_start = True
        return self.tasks

    def _func_wrapper(self, task_id):
        """
        Wraps the processing function and handles concurrency.
        """
        logger.debug(f"Name: {self.__name__}, id: {task_id} start")
        while self.is_start:
            data = None
            try:
                if not self.no_input:
                    with self.get_data_lock:
                        data = next(self.get_data_generator)
                    if isinstance(data, NodeStop):
                        raise NodeStop()
                    self.executing_data_queue.append(data)
                result = self._proc_data(data)
                self._put_data(result)
            except NodeStop:
                logger.info(f"Node {self.__name__} No. {task_id} stop")
                break
            finally:
                if data in self.executing_data_queue:
                    self.executing_data_queue.remove(data)
            if task_id == 0 and self._is_upstream_end():
                logger.info(f"Node {self.__name__} No. {task_id} upstream end")
                self.end()
                break
            sleep(0)
        if all(task.ready() for task in self.tasks if task != gevent.getcurrent()):
            logger.info(f"Node {self.__name__} No. {task_id} all other tasks finished")
            self.is_start = False
            
    def _get_data(self):
        while self.is_start:
            data = self.src_queue.get()
            yield from self._get_one_data(data)
        yield NodeStop()

    def _get_one_data(self, data):
        if isinstance(data, NodeStop):
            yield NodeStop()
        if self.is_data_iterable:
            assert isinstance(
                data, Iterable
            ), f"Unpack decorator only supports single iterable data, current node: {self.__name__}, current data: {data}"
            for d in data:
                yield d
        else:
            yield data

    def _put_data(self, data):
        """
        Puts data to the destination queue.
        """
        if self.discard_none_output and data is None:
            return
        for node in self.dst_nodes.values():
            if not self.criterias.get(node.__name__, None) or self.criterias[
                node.__name__
            ](data):
                if self.put_deepcopy_data:
                    node.put(copy.deepcopy(data))
                else:
                    node.put(data)

    def _error_decorator(self, func):
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(max=10),
            retry=retry_if_exception_type(Exception),
        )
        @functools.wraps(func)
        def input_wrapper(data):
            if self.no_input:
                result = func()
            else:
                result = func(data)
            return result

        @functools.wraps(func)
        def error_wrapper(data):
            try:
                return input_wrapper(data)
            except Exception as e:
                logger.error(
                    f"{self.__name__} error: {e}, input_data: {data}"
                    f"Error stack:\n{traceback.format_exc()}"
                )
                if DEBUG_MOD:
                    raise e
                else:
                    error_stack = traceback.format_exc()
                    return NodeProcessingError((data), self.__name__, e, error_stack)

        return error_wrapper

    def _is_upstream_end(self):
        if self.src_nodes and all(
            node.is_start == False for node in self.src_nodes.values()
        ):
            return True
        else:
            return False
