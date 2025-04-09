import time
import threading
import logging
from datetime import timedelta

from .analyser import Analyser
from .singleton_meta import SingletonMeta

logger = logging.getLogger(__name__)


class Monitor(metaclass=SingletonMeta):
    def __init__(self, report_interval=10) -> None:
        self.registered_analysers = []
        self.start_time = None
        self.report_interval = report_interval

    def start(self):
        for analyser in self.registered_analysers:
            analyser.start()
        self.thread = threading.Thread(target=self.get_all_info)
        self.thread.start()
        self.start_time = time.time()

    def get_all_info(self):
        while True:
            time.sleep(self.report_interval)
            total_time = time.time() - self.start_time
            readable_time = str(timedelta(seconds=total_time))
            logger.info("=" * 80 + f"\nTotal execution time: {readable_time}")
            for analyser in self.registered_analysers:
                string = analyser.report()
                logger.info("=" * 80 + "\n" + string)

    def register(self, *analysers):
        for analyser in analysers:
            assert isinstance(analyser, Analyser)
            self.registered_analysers.append(analyser)
