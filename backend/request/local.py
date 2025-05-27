import os
import requests
from requests.exceptions import HTTPError
import json

from collections import defaultdict
from json.decoder import JSONDecodeError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
    retry_if_exception_type
)
import logging
logger = logging.getLogger(__name__)


class LocalRequest:
    def __init__(self, port):
        self.url = f"http://localhost:{port}/infer"
        logger.warning(f"Token counter is not supported in LocalRequest, each request will be counted as 1 token")

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(30),
        retry=retry_if_exception_type((JSONDecodeError, HTTPError)) # 如果不是这几个错就不retry了
    )
    def completion(self, messages, **kwargs):
        try:
            config = self._format_config_params(kwargs)
            data = {"instances": [messages], "params": config}
            result = requests.post(
                self.url, json=data, headers={"Content-Type": "application/json"}
            )
            result.raise_for_status()
            answer = json.loads(result.content)[0]
        except JSONDecodeError as e:
            logger.error(
                f"JSONDecodeError in LocalRequest.completion: {e}\nResult: {result.content}"
            )
            raise
        except HTTPError as e:
            logger.warning(f"HTTPError in LocalRequest.completion: {e}\nResult: {result.content}")
            raise
        except Exception as e:
            logger.error(f"Unexpected Error in LocalRequest.completion: {e}\n")
            raise
        return answer, 1

    def _format_config_params(self, kwargs):
        config = {}
        for key, value in kwargs.items():
            config[key] = value
        return config