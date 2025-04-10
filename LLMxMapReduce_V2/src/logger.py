import logging
import sys

def setup_logger():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s:%(lineno)d]\n%(message)s\n',
                                  datefmt='%Y-%m-%d-%H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    return root_logger

logger = setup_logger()