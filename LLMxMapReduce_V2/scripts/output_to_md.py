import json
import os

input_file = ""
output_dir = ""

with open(input_file, "r") as f:
    for line in f:
        data = json.loads(line)
        content = data["content"]
        content += "\n\n" + data["ref_str"]
        with open(os.path.join(output_dir, data["title"] + ".md") , "w") as out:
            out.write(content)