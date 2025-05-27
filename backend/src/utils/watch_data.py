import json
import os
from typing import List
from datetime import datetime, timedelta


def split_data_to_md(data, save_dir):
    title = data["title"]
    content = data["content"]
    outline = data["skeleton"]
    save_dir = os.path.join(save_dir, title)
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, "content.md"), "w") as f:
        f.write(content)
    with open(os.path.join(save_dir, "skeleton.md"), "w") as f:
        f.write(outline)
    for digest in data["digests"]:
        digest_title = digest["bibkey"]
        digest_content = digest["content"]
        with open(os.path.join(save_dir, f"{digest_title}.md"), "w") as f:
            f.write(digest_content)


def split_different_block(source):
    block_data = {}
    with open(source, "r") as f:
        for data in f:
            data = json.loads(data)
            bloc_count = data["block_cycle_count"]
            if bloc_count not in block_data:
                block_data[bloc_count] = []
            block_data[bloc_count].append(data)

    data_title = None
    sampled_data = None
    source_dir = os.path.dirname(source)
    for block_count, data in block_data.items():
        save_file = source.replace(".jsonl", f"_block_{block_count}.jsonl")
        with open(save_file, "w") as f:
            for d in data:
                f.write(json.dumps(d) + "\n")

                if data_title is None:
                    data_title = d["title"]
                    sampled_data = d
                else:
                    if d["title"] == data_title:
                        sampled_data = d

        with open(
            os.path.join(source_dir, f"block_{block_count}_sample.json"), "w"
        ) as f:
            f.write(json.dumps(sampled_data, indent=4))

        with open(
            os.path.join(source_dir, f"block_{block_count}_sample_outline.md"), "w"
        ) as f:
            f.write(sampled_data["skeleton"])


def calculate_time_cost(source):
    block_data = {}
    with open(source, "r") as f:
        for data in f:
            data = json.loads(data)
            bloc_count = data["block_cycle_count"]
            if bloc_count not in block_data:
                block_data[bloc_count] = []
            block_data[bloc_count].append(data)

    for block_count, data in block_data.items():
        total_time = timedelta()
        for d in data:
            # "cost_time": "04:16:10",
            time_parts = datetime.strptime(d["cost_time"], "%H:%M:%S")
            total_time += timedelta(
                hours=time_parts.hour,
                minutes=time_parts.minute,
                seconds=time_parts.second,
            )

        average_time = total_time / len(data)
        hours, remainder = divmod(average_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)

        print(
            f"block_count: {block_count}, average_time: {int(hours):02}:{int(minutes):02}:{int(seconds):02}"
        )


def extract_data(source, target_path: str, require_titles: List[str]):
    filter_data = []
    for data in source:
        if data["title"] in require_titles:
            filter_data.append(data)

    with open(target_path, "w") as f:
        for data in filter_data:
            f.write(json.dumps(data) + "\n")
            
def cal_avg_len(file_path):
    with open(file_path, "r") as f:
        total_len = 0
        total_count = 0
        for data in f:
            data = json.loads(data)
            total_len += len(data["content"])
            total_count += 1
    print(f"Data: {file_path}, Average length: {total_len / total_count}")
