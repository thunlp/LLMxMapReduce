# # google_request.py
# import os
# import logging
# from google import genai
# from google.genai import types
# from tenacity import (
#     retry,
#     stop_after_attempt,
#     wait_random_exponential,
#     retry_if_exception_type
# )

# logger = logging.getLogger(__name__)

# proxy = "http://127.0.0.1:7890"
# os.environ["HTTPS_PROXY"] = proxy
# print(f"Set HTTPS_PROXY to {proxy} in google_request.py")

# from google import genai

# class GoogleRequest:
#     def __init__(self, model: str):
#         self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
#         self.model = model

#     @retry(
#         wait=wait_random_exponential(multiplier=2, max=60),
#         stop=stop_after_attempt(10),
#         retry=retry_if_exception_type(Exception)  # 网络、限流、服务端错误等都重试
#     )
#     def completion(self, messages, **kwargs) -> str:

#         contents = [
#             {"role": m["role"], "parts": [types.Part.from_text(text=m["content"])]}
#             for m in messages
#         ]
            
#         # 调用生成接口
#         response = self.client.models.generate_content(
#             model=self.model,
#             contents=contents,
#             config=genai.types.GenerateContentConfig(
#                 thinking_config=genai.types.ThinkingConfig(
#                 thinking_budget=1024
#                 )
#             )
#         )
        
#         text = getattr(response, "text", None)
#         if not text:
#             logger.error("GoogleRequest.completion: empty response.text")
#             raise ValueError("Empty response from GoogleRequest")
#         return text
