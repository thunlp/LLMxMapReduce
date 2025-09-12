import json
import os
import argparse

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f","--input_file", type=str, required=True, help="Path to the input JSONL file")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    input_file = args.input_file
    output_dir = os.path.dirname(input_file)

    with open(input_file, "r") as f:
        for line in f:
            data = json.loads(line)
            content = data["content"]
            content += "\n\n" + data["ref_str"]
            with open(os.path.join(output_dir, data["title"] + ".md") , "w") as out:
                out.write(content)