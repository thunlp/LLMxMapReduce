import os
import json
from typing import List, Dict
from gevent.lock import Semaphore
from .local import LocalRequest
from .openai import OpenAIRequest
# from .google import GoogleRequest
import requests

import logging
logger = logging.getLogger(__name__)


class RequestWrapper:
    _connection_semaphore = {}

    def __init__(self, model="gemini-2.5-flash", infer_type="OpenAI", connection=40, port=None):
        if not model:
            model = "gemini-2.5-flash"
        
        print(f"using model={model}")
        self.request_pool = None
        self.model = model
        self._connection_semaphore[model] = Semaphore(connection)
        # infer_type = "Google"
        if infer_type == "OpenAI":
            self.request_pool = OpenAIRequest(model=model)
        elif infer_type == "local":
            self.request_pool = LocalRequest(port=port)
        # elif infer_type == "Google":
        #     self.request_pool = GoogleRequest(model=model)
        else:
            raise ValueError(
                f"Invalid infer_type: {infer_type}, should be OpenAI or local"
            )

    def completion(self, message, **kwargs):
        logger.debug(f"Requesting completion sending")
        if isinstance(message, str):
            message = [{"role": "user", "content": message}]
        elif isinstance(message, List):
            if not all(
                isinstance(m, Dict)
                and "role" in m
                and "content" in m
                and isinstance(m["role"], str)
                and isinstance(m["content"], str)
                for m in message
            ):
                raise ValueError(
                    "message should be a List[Dict['role':str, 'content':str]]"
                )
        if self.model in self._connection_semaphore:
            with self._connection_semaphore[self.model]:
                logger.debug(f"Acquired semaphore for {self.model} (remain={self._connection_semaphore[self.model].counter})")
                result = self.request_pool.completion(message, **kwargs)
        else:
            result = self.request_pool.completion(message, **kwargs)
        logger.debug(f"Requesting completion received")
        if not result:
            raise ValueError(
                f"Requesting completion failed, return with empty result, message length: {len(str(message))}"
            )
        
        # usage = result.get("usage", {})
        # prompt_tokens = usage.get("prompt_tokens", None)
        # completion_tokens = usage.get("completion_tokens", None)
        # total_tokens = usage.get("total_tokens", None)

        # logger.info(
        #     f"[{self.model}] token 使用情况："
        #     f"prompt_tokens={prompt_tokens}, "
        #     f"completion_tokens={completion_tokens}, "
        #     f"total_tokens={total_tokens}"
        # )
        return result

    async def async_request(self, messages, **kwargs):
        """异步版本的completion方法，与同步版本功能相同"""
        import asyncio
        import functools

        # 在线程池中执行同步的completion方法
        loop = asyncio.get_event_loop()
        # 使用functools.partial来传递关键字参数
        func = functools.partial(self.completion, messages, **kwargs)
        return await loop.run_in_executor(None, func)
