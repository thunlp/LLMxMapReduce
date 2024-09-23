import argparse
import json
import os 
p = argparse.ArgumentParser(
    description='get process args')
p.add_argument('--result_dir', type=str, default='eval/result', help='Path to save the output file')
p.add_argument('--output_dir', type=str, default=None, help='Path to save the output file')

p.add_argument('--overwrite', action='store_true', default=False)

args = p.parse_args()

ALL_TASKS = [
    "passkey",
    "number_string",
    "kv_retrieval",
    "longdialogue_qa_eng",
    "longbook_sum_eng",
    "longbook_choice_eng",
    "longbook_qa_eng",
    "longbook_qa_chn",
    "math_find",
    "math_calc",
    "code_run",
    "code_debug",
]
ans_prefixes = [

    # "final answer is",
    # "Therefore",
    "Answer:",
    "答案："

]
def task_special_process(pred,task):
    for prefix in ans_prefixes:
        idx = pred.rfind(prefix)
        if idx == -1:
            continue
        # The prediction ends with this prefix
        if len(pred) < idx + len(prefix) + 1:
            break
        after_prefix = pred[idx + len(prefix) + 1:]
        # after_prefix = pred[idx:]
        
        if task in ['code_debug','longbook_choice_eng']:  # code_debug needs to be prefixed with "answer:" to process, otherwise it will only determine whether the first character is ABCD. If "\nA" appears, there will be problems.
            pred = "answer: " + after_prefix
            return pred
        if task in ["longbook_qa_eng",'longbook_qa_chn',"longdialogue_qa_eng", 'longbook_sum_eng']:  # need to remove
            pred = after_prefix
            for p in ['置信度分数：','Confidence Score:']:
                idx = pred.rfind(p)
                if idx != -1:
                    pred = pred[:idx]
            return pred
    
    return pred
    
if args.output_dir == None:
    os.makedirs(os.path.join(args.result_dir, 'processed'),exist_ok=True)
    args.output_dir = os.path.join(args.result_dir, 'processed')
for task in ALL_TASKS:
    file_name = f'preds_{task}.jsonl'
    if file_name in os.listdir(args.result_dir):
        with open(os.path.join(args.result_dir,file_name)) as f:
            with open(os.path.join(args.output_dir,file_name), mode='w+') as fw:
                json_lines = f.readlines()
                for jsonl in json_lines:
                    data = json.loads(jsonl)
                    pred = data['prediction']
                    pred = task_special_process(pred,task)
                    data['prediction'] = pred

                    fw.write(json.dumps(data,ensure_ascii=False)+'\n')