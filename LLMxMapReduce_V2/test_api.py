from request import RequestWrapper


request_pool = RequestWrapper(
    model="gemini-2.0-flash-thinking-exp-01-21", infer_type="OpenAI"
)

prompt = "What is the capital of France?"

response = request_pool.completion(prompt)
print(response)
