import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--jsonl_file",
        type=str,
        help="Path to the input JSONL file",
    )
    parser.add_argument(
        "--saving_path",
        default="./output/eval",
        type=str,
        help="Directory containing the output survey",
    )
    parser.add_argument(
        "--eval_model",
        default="gemini-2.0-flash-thinking-exp-1219",
        type=str,
        help="Model for evaluation",
    )
    parser.add_argument(
        "--infer_type",
        default="OpenAI",
        type=str,
        help="Specify OpenAI or local",
    )
    parser.add_argument(
        "--method_name",
        default="LLMxMRv2",
        type=str,
        help="Method name of output jsonl file",
    )

    args = parser.parse_args()
    return args