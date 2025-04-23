# google_request.py
import os
import logging
from google import genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)

proxy = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"]  = proxy
os.environ["http_proxy"]  = proxy
os.environ["HTTPS_PROXY"] = proxy
os.environ["https_proxy"] = proxy


from google import genai

class GoogleRequest:
    def __init__(self, model: str):
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        self.model = model

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Exception)  # 网络、限流、服务端错误等都重试
    )
    def completion(self, messages, **kwargs) -> str:
        # 支持单字符串和 role/content 列表
        if isinstance(messages, str):
            contents = messages
        else:
            # 转换为 genai 期望的多轮对话格式
            contents = [
                {"role": m["role"], "parts": [m["content"]]}
                for m in messages
            ]

        # 调用生成接口
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=contents,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(
                thinking_budget=1024
                )
            )
        )
        
        text = getattr(response, "text", None)
        if not text:
            logger.error("GoogleRequest.completion: empty response.text")
            raise ValueError("Empty response from GoogleRequest")
        return text
