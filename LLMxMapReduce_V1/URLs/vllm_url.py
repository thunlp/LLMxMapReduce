import argparse
import os

from flask import Flask, jsonify, request
from vllm import LLM, SamplingParams

"""
reference:https://github.com/vllm-project/vllm/blob/main/vllm/sampling_params.py
"""

parser = argparse.ArgumentParser()
parser.add_argument("--model_name", type=str, help="Model name on hugginface")
parser.add_argument("--gpuid", type=str, default="0", help="GPUid to be deployed")
parser.add_argument("--port", type=int, default=5002, help="the port")
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.gpuid

llm = LLM(
    model=args.model_name,
    trust_remote_code=True,
    tensor_parallel_size=len(args.gpuid.split(",")),
)

# Model parameters
params_dict = {
    "n": 1,
    "best_of": None,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "temperature": 1.0,
    "top_p": 1.0,
    "top_k": -1,
    "use_beam_search": False,
    "length_penalty": 1.0,
    "early_stopping": False,
    "stop": None,
    "stop_token_ids": None,
    "ignore_eos": False,
    "max_tokens": 16,
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
    app.run(port=args.port, debug=False)
