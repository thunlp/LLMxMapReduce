import json
import random

from async_d import Node
from async_d import Sequential
from gevent.fileobject import FileObject

from src.data_structure.survey import Survey
import logging
logger = logging.getLogger(__name__)


class EncodePipeline(Sequential):
    def __init__(self, configs, data_num, output_file, worker_num=1):
        self.configs = configs
        self.worker_num = worker_num
        self.data_num = data_num

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
                if (self.data_num != None and self.data_num <= 0):
                    break
                survey = Survey(json.loads(line))
                if self.data_num != None:
                    self.data_num -= 1
                yield survey
            else:
                logger.info("All data in input file has been loaded.")
        if self.data_num != None and self.data_num > 0:
            logger.warning(f"Only {self.data_num} data in input file, less than specified data_num.")
        return

    def unpack(self, survey):
        return survey
