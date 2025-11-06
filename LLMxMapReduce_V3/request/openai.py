import os
from .decorators import *
from openai import OpenAI, InternalServerError, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
    retry_if_exception_type
)
import logging
logger = logging.getLogger(__name__)

@track_completion_calls
class OpenAIRequest:
    _calls_count = 0
    _token_usage_history = []

    def __init__(self, model):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL", ""),
        )
        self.model = model

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(100),
        retry=retry_if_exception_type((RateLimitError, InternalServerError, APIError)) # 如果不是这几个错就不retry了
        )
    def completion(self, messages, **kwargs):
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, **kwargs
            )

            if not response.choices or len(response.choices) == 0:
                error_msg = "OpenAI API returned empty choices in response"
                logger.debug(error_msg)
                raise ValueError(error_msg)
            answer = response.choices[0].message.content

            token_usage = response.usage

            OpenAIRequest._token_usage_history.append({
                "model": self.model,
                "completion_tokens": token_usage.completion_tokens,
                "prompt_tokens": token_usage.prompt_tokens,
                "total_tokens": token_usage.total_tokens
            })

        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded in OpenAIRequest.completion: {e}")
            raise 
        except InternalServerError as e:
            logger.warning(f"Internal server error in OpenAIRequest.completion: {e}")
            # logger.warning(f"Prompt: {messages}")
            raise 
        except Exception as e:
            logger.error(f"Unexpected error in OpenAIRequest.completion: {e}. messages: \n{messages}")
            raise 

        return answer

    @retry(
            wait=wait_random_exponential(multiplier=2, max=60),
            stop=stop_after_attempt(10),
            retry=retry_if_exception_type((RateLimitError, InternalServerError, APIError))
        )
    def chat(self, messages):
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return completion.choices[0].message.content
