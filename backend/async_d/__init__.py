import gevent
import sys
import logging
import trio # do not delete this line, it will be effected by monkey patch that will cause fault
from gevent import monkey
monkey.patch_all()

logger = logging.getLogger(__name__)
logger.info("Monkey patching gevent in async_d")

gevent.get_hub().exception_stream = sys.stderr

import json

try:
    with open("./config/async_dfd_config.json", "r") as f:
        ASYNC_D_CONFIG = json.load(f)
except FileNotFoundError:
    ASYNC_D_CONFIG = {}

from .node import Node, decorator
from .node_group.pipeline import Pipeline
from .node_group.sequential import Sequential
from .analyser import Analyser, Monitor, PipelineAnalyser

__all__ = [
    "Node",
    "Pipeline",
    "Sequential",
    "Analyser",
    "Monitor",
    "PipelineAnalyser",
    "decorator",
]
