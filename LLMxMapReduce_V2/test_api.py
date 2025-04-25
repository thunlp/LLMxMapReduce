from request import RequestWrapper


request_pool = RequestWrapper(model="gemini-2.5-flash-preview-04-17", infer_type="Google")

prompt = "What is the capital of France?"

response = request_pool.completion(prompt)
print(response)