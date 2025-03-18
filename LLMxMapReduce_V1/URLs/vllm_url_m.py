import os

from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer
from vllm import LLM, SamplingParams

from URLs.dispatcher import GPUDispatcher as gdp

gdp.bind_worker_gpus()

"""
reference:https://github.com/vllm-project/vllm/blob/main/vllm/sampling_params.py
"""

model_name = os.environ.get("HF_MODEL_NAME")
per_proc_gpus = int(os.environ.get("PER_PROC_GPUS"))
quantization = os.environ.get("QUANTIZATION")
port = os.environ.get('PORT')
if quantization == 'None' or quantization ==None:
    quantization = None
print('Load Model')
print(f"model_name:{model_name}, per_proc_gpus:{per_proc_gpus}")
max_model_len = os.environ.get("MAX_MODEL_LEN")
if max_model_len == 'None' or max_model_len == None:
    max_model_len = None
else:
    max_model_len = int(max_model_len)

llm = LLM(model=model_name, trust_remote_code=True,
          tensor_parallel_size=per_proc_gpus, quantization=quantization, enforce_eager=True, gpu_memory_utilization=1,max_model_len=max_model_len)
# Model parameters
params_dict = {
    "n": 1,
    "best_of": 1,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": -1,
    "use_beam_search": False,
    "length_penalty": 1.0,
    "early_stopping": False,
    "stop": None,
    "stop_token_ids": None,
    "ignore_eos": False,
    "max_tokens": 1000,
    "logprobs": None,
    "prompt_logprobs": None,
    "skip_special_tokens": True,
}

print("model load finished")

app = Flask(__name__)


@app.route("/infer", methods=["POST"])
def main():
    datas = request.get_json()
    params = datas["params"]
    prompts = datas["instances"]

    for key, value in params.items():
        if key in params_dict:
            params_dict[key] = value

    outputs = llm.generate(prompts, SamplingParams(**params_dict))

    res = []
    if "prompt_logprobs" in params and params["prompt_logprobs"] is not None:
        for output in outputs:
            prompt_logprobs = output.prompt_logprobs
            logp_list = [list(d.values())[0] for d in prompt_logprobs[1:]]
            res.append(logp_list)
        return jsonify(res)

    else:
        for output in outputs:
            generated_text = output.outputs[0].text
            res.append(generated_text)
        return jsonify(res)


if __name__ == "__main__":
    http_server = WSGIServer(("127.0.0.1", port), app)
    http_server.serve_forever()
