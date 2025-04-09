import functools
import logging

from ..label import LabelData

logger = logging.getLogger(__name__)


def skip_data_decorator(func):
    @functools.wraps(func)
    def skip_wrapper(data):
        if isinstance(data, Exception):
            return data

        result = func(data)
        return result

    return skip_wrapper


def label_proc_decorator(func):
    @functools.wraps(func)
    def labeled_wrapper(label_data):
        assert isinstance(label_data, LabelData)
        label = label_data.label
        result = func(label_data.data)
        ret_data = LabelData(result, label)
        return ret_data

    return labeled_wrapper
