from copy import deepcopy
from logging import config
import traceback
import argparse
import time
import sys
sys.path.append('/path/to/the/project')
from eval_utils import (
    create_msgs,
    load_data,
    dump_jsonl,
    iter_jsonl,
    get_answer,
)
import os
from pathlib import Path
import json
import logging
import tiktoken
from openai import OpenAI
import pdb
import sys

from pipeline import BasePipeline
from utils import read_yaml




if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description='Generate test in infbench')
    p.add_argument('--overwrite', action='store_true', default=False)
    p.add_argument('--chunk_size', type=int, default=4096)
    p.add_argument(
        "--task",
        type=str,
        # choices=list(DATA_NAME_TO_MAX_NEW_TOKENS.keys()) + ["all"],
        required=True,
        help="Which task to use. Note that \"all\" can only be used in `compute_scores.py`.",  # noqa
    )
    p.add_argument(
        '--data_dir',
        type=str,
        default='data',
        help="The directory of data."
    )
    p.add_argument('--config_file', type=str,
                   default='config/qa.yaml')
    p.add_argument("--output_dir", type=str, default="eval/result/infinitebench", help="Where to dump the prediction results.")  # noqa

    p.add_argument(
        "--prompt_name",
        type=str,
        choices=["gpt-3.5-turbo", "gpt4", "yarn-mistral", "kimi",
            "claude2", 'minicpm_cn', 'minicpm', "rwkv", "yi-6b-200k", "yi-34b-200k", "chatglm3", 'MiniCPM-2B-dpo-bf16', 'MiniCPM-2B-sft-bf16'],
        default="gpt4",
        help="Our prompt is base on gpt4's prompt.",  # noqa
    )
    p.add_argument("--start_idx", type=int, default=0,
                   help="The index of the first example to infer on. This is used if you want to evaluate on a (contiguous) subset of the data.")  # noqa
    p.add_argument("--stop_idx", type=int,
                   help="The index of the last example to infer on. This is used if you want to evaluate on a (contiguous) subset of the data. Defaults to the length of dataset.")  # noqa
    p.add_argument("--verbose", action='store_true')
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--print_intermediate_path", type=str, default=None)
    args = p.parse_args()

    logger = logging.getLogger('main')
    logger.setLevel(level=logging.INFO)

    # Handler
    handler = logging.FileHandler(args.output_dir + '/log.log')
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    verbose = args.verbose
    task = args.task

    examples = load_data(task, args.data_dir)

    result_dir = Path(args.output_dir)
    result_dir.mkdir(exist_ok=True, parents=True)

    output_path = result_dir / f"preds_{args.task}.jsonl"
    if output_path.exists():
        preds = list(iter_jsonl(output_path))
        start_idx = len(preds)
        stop_idx = len(examples)
    else:
        start_idx = 0
        stop_idx = len(examples)
        preds = []
    tokenizer = None 
    if args.start_idx:
        start_idx += args.start_idx
    start_time = time.time()
    i = start_idx
    if args.stop_idx:
        stop_idx = args.stop_idx
    map_reduce_config = read_yaml(args.config_file)
    while i < stop_idx:
        eg = examples[i]
        id = eg["id"]
        msgs, prompt, context = create_msgs(
            tokenizer, eg, task, model_name=args.prompt_name, data_dir=args.data_dir
        )
        # logger.info(
        #     f'--------------------------------------Example {i} of {stop_idx}--------------------------------------')
        print(f"======== Example {i} of {stop_idx} =========")
        if verbose:
            print(f"======== Example {i} =========")
            print("Input text:")
            print(prompt[:300])
            print("...")
            print(prompt[-300:])
            print("==============================")
        # Make prediction
        # try:
            # response = chat(msgs)
            # pdb.set_trace()
        try:
            pipline = BasePipeline(
                map_reduce_config, print_intermediate_path=args.print_intermediate_path, doc_id=id)
            result = pipline.run(doc=context,question=prompt,chunk_size=args.chunk_size)
        except Exception as e:

            result = traceback.format_exc()
            print("ERROR:", result)
        pred = result.strip()

        preds.append(
            {
                "id": id,
                "prediction": pred,
                "ground_truth": get_answer(eg, task),
            }
        )
        # Save result
        dump_jsonl(preds, output_path)
        print("Time spent:", round(time.time() - start_time))
        # exit()
        # print(response)
        # time.sleep(10)
        i += 1

        '''except Exception as e:
            print("ERROR:", e)
            preds.append(
                {
                    "id": i,
                    "prediction": "",
                    "ground_truth": get_answer(eg, task),
                }
            )
            print("Abandoning...")
            i += 1
            # time.sleep(10)'''
