from abc import ABC, abstractmethod
from typing import Dict, Optional

from gevent import spawn, joinall
from gevent.lock import Semaphore

from src.base_method.data import Dataset
import logging
logger = logging.getLogger(__name__)



def parallel_semaphore_decorator(func):
    def wrapper(self, *args, **kwargs):
        with self._parallel_semaphore:
            return func(self, *args, **kwargs)

    return wrapper


class Module(ABC):
    _parallel_count = 20

    def __init__(self, *args, **kwargs):
        self.__name__ = type(self).__name__
        self._modules: Dict[str, Module] = {}
        self._parallel_semaphore = Semaphore(Module._parallel_count)

    def __call__(self, *args, **kwargs):
        def get_task_result(task):
            try:
                return task.value
            except Exception as e:
                return e
            
        try:
            if len(args) == 1 and isinstance(args[0], Dataset):
                tasks = []
                batch_data = args[0]
                for data in batch_data:
                    tasks.append(
                        spawn(
                            self.forward, *data, **kwargs
                        )
                    )
                joinall(tasks)
                return [get_task_result(task) for task in tasks]
            else:
                task = spawn(
                    self.forward, *args, **kwargs
                )
                task.join()
                return get_task_result(task)
        except Exception as e:
            logger.error(f"Error in {self.__name__}: {e}")
            raise

    @abstractmethod
    @parallel_semaphore_decorator
    def forward(self, *args, **kwargs):
        pass

    def add_module(self, name: str, module: Optional["Module"]) -> None:
        if not isinstance(module, Module) and module is not None:
            raise TypeError(f"{type(module)} is not a Module subclass")
        elif not isinstance(name, str):
            raise TypeError(
                f"module name should be a string. Got {type(name)}"
            )
        elif hasattr(self, name) and name not in self._modules:
            raise KeyError(f"attribute '{name}' already exists")
        elif "." in name:
            raise KeyError(f'module name can\'t contain ".", got: {name}')
        elif name == "":
            raise KeyError('module name can\'t be empty string ""')
        self._modules[name] = module

    def _get_name(self):
        return self.__class__.__name__
