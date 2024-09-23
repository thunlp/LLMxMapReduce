from argparse import ArgumentParser, Namespace
from eval_utils import DATA_NAME_TO_MAX_NEW_TOKENS
import argparse

def parse_args() -> Namespace:
    p = argparse.ArgumentParser(
        description='infinitebench task')
    # p.add_argument('--output_dir', type=str, default='eval/result', help='Path to save the output file')
    # p.add_argument('--model_name', type=str, default='gpt-3.5-turbo')
    p.add_argument('--log_file', type=str,
                   default='eval/result/infinitebench/eval.log')
    p.add_argument('--overwrite', action='store_true', default=False)
    p.add_argument('--chunk_size', type=int, default=3900)
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
    p.add_argument("--output_dir", type=str, default="eval/result/infinitebench", help="Where to dump the prediction results.")  # noqa
    p.add_argument(
        "--model_path",
        type=str,
        help="The path of the model (in HuggingFace (HF) style). If specified, it will try to load the model from the specified path, else, it wll default to the official HF path.",
        # noqa
    )  # noqa
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

    args = p.parse_args()
    return args