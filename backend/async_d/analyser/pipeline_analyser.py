import time
import functools
import logging
from gevent.lock import Semaphore
from collections import defaultdict
from tabulate import tabulate

from .analyser import Analyser

logger = logging.getLogger(__name__)


class PipelineAnalyser(Analyser):

    class FuncInfo:
        def __init__(self, func):
            self.func = func
            self.exec_count = 0
            self.exec_time = 0
            self.interval_exec_count = 0
            self.interval_exec_time = 0

    def __init__(self):
        self.node_group = None
        self.node_executing_count = {}
        self.func_info = {}
        self.func_lock = defaultdict(Semaphore)

    def start(self):
        from ..node import Node

        def add_decorator(node_group):
            for node in node_group.all_nodes.values():
                if isinstance(node, Node):
                    self.func_info[node.__name__] = self.FuncInfo(node._proc_data)
                    node.add_proc_decorator(self.decorator)
                else:
                    add_decorator(node)

        add_decorator(self.node_group)

    def decorator(self, func):
        @functools.wraps(func)
        def exec_time_wrapper(*args, **kwargs):
            func_name = func.__name__
            func_info = self.func_info[func_name]

            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            exec_time = end_time - start_time
            with self.func_lock[func_name]:
                func_info.interval_exec_time += exec_time
                func_info.interval_exec_count += 1

            return result

        return exec_time_wrapper

    def register(self, node_group):
        self.node_group = node_group

    def report(self) -> str:
        from .. import Node

        table = []
        headers = [
            "Serial",
            "Name",
            "Wait",
            "Exec",
            "Speed",
            "Avg Speed",
        ]

        def add_infos(node_group, cur_table):
            for node in node_group.all_nodes.values():
                if isinstance(node, Node):
                    info = self.func_info[node.__name__]
                    with self.func_lock[node.__name__]:
                        interval_exec_count = info.interval_exec_count
                        info.exec_count += interval_exec_count
                        total_exec_count = info.exec_count

                        interval_exec_time = info.interval_exec_time
                        info.exec_time += interval_exec_time
                        total_exec_time = info.exec_time

                        info.interval_exec_count = 0
                        info.interval_exec_time = 0
                        
                    name = node.__name__
                    if node.is_start:
                        name = f"{name} (Running)"
                    else:
                        name = f"{name} (Finished)"
                        
                    cur_table.append(
                        [
                            "-".join(map(str, node.serial_number)),
                            name,
                            f"{node.src_queue.qsize()}/{node.src_queue.maxsize}",
                            f"{len(node.executing_data_queue)}/{node.worker_num}",
                            (
                                f"{interval_exec_count}/{interval_exec_time:.2f}s, {interval_exec_count / interval_exec_time:.2f}/s"
                                if interval_exec_time > 0
                                else "N/A"
                            ),
                            (
                                f"{total_exec_count}/{total_exec_time:.2f}s, {total_exec_time / total_exec_count:.2f}/s"
                                if total_exec_count > 0
                                else "N/A"
                            ),
                        ]
                    )
                else:
                    add_infos(node, cur_table)

        add_infos(self.node_group, table)

        string = "Pipeline Report"
        string += "\n" + tabulate(table, headers, tablefmt="grid")
        return string
