import json
import random

from async_d import Node
from async_d import Sequential
from gevent.fileobject import FileObject
from threading import Lock

from src.data_structure.survey import Survey
import logging
logger = logging.getLogger(__name__)


class EncodePipeline(Sequential):
    def __init__(self, configs, data_num, worker_num=1):
        self.configs = configs
        self.worker_num = worker_num
        self.data_num = data_num
        self.processed_count = 0
        self._count_lock = Lock()

        self.load_node = Node(
            self.load_survey, worker_num=self.worker_num
        )
        self.unpack_node = Node(
            self.unpack,
            is_data_iterable=True,
            worker_num=self.worker_num,
        )
        
        super().__init__(
            [
                self.load_node,
                self.unpack_node,
            ]
        )

    def load_survey(self, input_file):
        with FileObject(input_file, "r") as f:
            for line in f:
                with self._count_lock:
                    if self.data_num is not None:
                        if self.processed_count >= self.data_num:
                            break
                        self.processed_count += 1
                
                survey = Survey(json.loads(line))
                yield survey
            else:
                logger.info("All data in input file has been loaded.")
        
        with self._count_lock:
            if self.data_num is not None and self.processed_count < self.data_num:
                logger.warning(
                    f"Only {self.processed_count} data in input file, "
                    f"less than specified data_num {self.data_num}."
                )
        return

    def unpack(self, survey):
        return survey
