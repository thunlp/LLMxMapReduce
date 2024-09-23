from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
import requests
from tqdm import tqdm
from vllm import LLM, SamplingParams
import os
from typing import Any, Callable, List

import openai
import tiktoken
import yaml



def print_intermediate_output(data):
    """
    Functions that print intermediate output

    parameter:
    data: Any type, intermediate data to be printed.
    """
    file_path = os.getenv('INTERMEDIATE_FILE_PATH')
    with open(file_path,mode='a+') as f:
        f.write(json.dumps(data)+'\n')


def print_intermediate_output(print_intermediate_path,input_data, output_data, type='map',doc_id=None):

    if not isinstance(input_data,list):
        input_data = [input_data]
    if not isinstance(output_data, list):
        output_data = [output_data]
    assert len(input_data) == len(output_data)
    file_path = print_intermediate_path
    # doc_id = os.getenv('DOC_ID')
    with open(file_path, mode='a+') as f:
        for index, i in enumerate(input_data):
            f.write(json.dumps({
                'input': i,
                'output': output_data[index],
                'operator_type': type,
                'doc_id': doc_id
            },ensure_ascii=False)+'\n')
            


# model_list =[]

def read_yaml(file_path):
    with open(file_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            return None


def split_list_of_docs(
    docs: List[str], length_func: Callable, token_max: int, **kwargs: Any
) -> List[List[str]]:
    """Split Documents into subsets that each meet a cumulative length constraint.

    Args:
        docs: The full list of Documents.
        length_func: Function for computing the cumulative length of a set of Documents.
        token_max: The maximum cumulative length of any subset of Documents.
        **kwargs: Arbitrary additional keyword params to pass to each call of the
            length_func.

    Returns:
        A List[List[Document]].
    """
    new_result_doc_list = []
    _sub_result_docs = []
    for doc in docs:
        _sub_result_docs.append(doc)
        _num_tokens = length_func(_sub_result_docs, **kwargs)
        if _num_tokens > token_max:
            if len(_sub_result_docs) == 1:
                raise ValueError(
                    "A single document was longer than the context length,"
                    " we cannot handle this."
                )
            new_result_doc_list.append(_sub_result_docs[:-1])
            _sub_result_docs = _sub_result_docs[-1:]
    new_result_doc_list.append(_sub_result_docs)
    return new_result_doc_list


data_prompt = {
    "params": {},
    "instances": [],
}


def run_thread_pool_sub(target, url: str, data, params, max_work_count: int):
    with tqdm(total=len(data)) as pbar:
        with ThreadPoolExecutor(max_workers=max_work_count) as t:
            futures = [t.submit(target, url, i, data[i], params)
                       for i in range(len(data))]
            for future in as_completed(futures):
                pbar.update(1)
                yield future.result()


def _post_request(url, data, params: dict):
    data_prompt={}
    data_prompt["instances"] = data
    data_prompt["params"] = params
    s = json.dumps(data_prompt)
    headers = {"Content-Type": "application/json"}

    backoff_time = 2
    backoff_count = 50
    i = 0
    while i < backoff_count:
        try:
            return requests.post(url, data=s, headers=headers).json()
        except Exception:
            time.sleep(backoff_time)
            backoff_time *= 1.5
            i += 1
    return "request time out"


def thread_function(url: str, idx: int, chk: List[Any], params: dict):
    lp = _post_request(url, chk, params)
    return idx, lp
