# $\text{LLM}\times\text{MapReduce}$: Simplified Long-Sequence Processing using Large Language Models

<p align="center">•
 <a href="#-introduction"> 📖Introduction </a> •
 <a href="#-news">🎉News</a> •
 <a href="#-features">✨Features</a> •
 <a href="#%EF%B8%8F-getting-started">⚡️Getting Started</a> 
</p>
<p align="center">•
 <a href="#-evaluation">📃 Evaluation</a> •
 <a href="#-experiment-results">📊Experiment Results</a> •
 <a href="#-citation">📝 Citation</a>•
 <a href="https://arxiv.org/abs/2410.09342">📃Paper</a>


</p>
</div>

# 📖 Introduction
Enlarging the context window of large language models (LLMs) has become a crucial research area, particularly for applications involving extremely long sequences. We introduce $\text{LLM}\times\text{MapReduce}$, a novel training-free framework for processing long sequences, utilizing a divide-and-conquer strategy to achieve comprehensive document understanding. The proposed $\text{LLM}\times\text{MapReduce}$ framework splits the entire document into several chunks for LLMs to read and then aggregates the intermediate answers to produce the final output. The main challenge for divide-and-conquer long-sequence processing frameworks lies in the risk of losing essential long-range information when splitting the document, which can lead the model to produce incomplete or incorrect answers based on the segmented texts. Disrupted long-range information can be classified into two categories: **inter-chunk dependency** and **inter-chunk conflict**.
We design **a structured information protocol** to better cope with inter-chunk dependency and **an in-context confidence calibration mechanism** to resolve inter-chunk conflicts. Experimental results demonstrate that $\text{LLM}\times\text{MapReduce}$ can outperform representative open-source and commercial long-context LLMs, and is applicable to several different models.

# ✨ Features

1. **Divide-and-Conquer Strategy**: The entire document is divided into chunks, which are processed individually by LLMs.
2. **Structured Information Protocol**: a structured information protocol ensures that crucial information flows between the map and reduce stages, preventing information loss when documents are split into chunks and enabling coherent answers for complex questions.

3. **In-Context Confidence Calibration Mechanism**: a dynamic mechanism that resolves conflicts between outputs from different chunks, ensuring the final result is accurate, consistent, and contextually aligned across the entire document.

<div align="center">
  <img src="assets/workflow.png" alt="$\text{LLM}\times\text{MapReduce}$ framework">
</div>




# ⚡️ Getting Started

To get started, ensure all dependencies listed in `requirements.txt` are installed. You can do this by running:

```bash
pip install -r requirements.txt
```

## Starting the Parallel Processing Backend


To enable parallel processing, you need to start the parallel processing backend. *If you plan to use the native OpenAI API or vLLM's OpenAI-Compatible Server instead, you can skip this section and refer to the [🔄 Alternative Option: Using OpenAI API](#-alternative-option-using-openai-api) section.*

To start the parallel processing backend, run the following command:

```bash
bash URLs/start_gunicorn.sh --hf-model-name=your/model/path --per-proc-gpus 2 --quantization None --cuda-visible-devices 0,1,2,3,4,5,6,7 --port=5002
```

Where:
* `--hf-model-name`: Specifies the path to your Hugging Face model.
* `--per-proc-gpus`: Defines the number of GPUs required per worker to load the model.
* `--quantization`: Specifies the quantization method applied to the model, or `None` if no quantization is used.
* `--cuda-visible-devices`: Lists the GPUs to be utilized. Ensure the number of GPUs matches the formula `per-proc-gpus * worker_num = len(cuda-visible-devices)`.
* `--port`: Specifies the port number on which the backend server will listen.
* `--max-model-len`: Model context length. If unspecified, will be automatically derived from the model config.

The `worker_num` is automatically calculated based on the formula `len(cuda-visible-devices) / per-proc-gpus`. While you don’t need to set it directly, you should ensure that `worker_num` is consistent with the `max_work_count` value set in your configuration when modifying the config later. A higher `worker_num` allows for more parallel processing, which can improve performance by enabling multiple tasks to be processed concurrently. However, ensure that you have sufficient GPU resources to support the number of workers.


We also provide example scripts located in `URLs/scripts`, which include the following models:

- **[Llama3-70b-instruct](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct)**: You can modify the provided script `URLs/scripts/start_Meta-Llama-3-70B-Instruct.sh`.
- **[Qwen2-72B-Instruct](https://huggingface.co/Qwen/Qwen2-72B-Instruct)**: You can adjust the settings in `URLs/scripts/start_Qwen2-72B-Instruct.sh`.
- **[MiniCPM3-4B](https://huggingface.co/openbmb/MiniCPM3-4B)**: Note that using MiniCPM3 requires setting up the environment. You can find the installation instructions in the [MiniCPM GitHub repository](https://github.com/OpenBMB/MiniCPM?tab=readme-ov-file#vllm). After setting up the environment, you can modify `URLs/scripts/start_MiniCPM3-4B.sh` to suit your setup.

You can modify these scripts according to your requirements to fit your specific setup.


## 🔄 Alternative Option: Using OpenAI API

If you prefer not to deploy the custom parallel processing backend, we also support two standardized approaches using OpenAI APIs:

### Option 1: Native OpenAI API
Directly use OpenAI's official API service. Simply add your API key to the config file. check out the [config modification guide](#modify-config) for details.

### Option 2: Self-hosted vLLM OpenAI API

Run the command to start your own OpenAI-Compatible Server:

```bash
python -m vllm.entrypoints.openai.api_server   \
    --model your/model/path \
    --served-model-name your-alias-name \
    --port 8080 \
    # --tensor-parallel-size 8
```

Ensure that the parameters in the command match those in your configuration file:  
- **`openai_api.name_or_path`** → `--model` (Local model path)  
- **`openai_api.model`** → `--served-model-name` (Your alias model name)  
- **`openai_api.base_url`** → `http://<host>:<port>/v1/` (`--port` should match)  
- **`openai_api.is_vllm_server`** → Set to `true` if using vLLM  
- **`tensor-parallel-size`** → Adjust as needed for multi-GPU execution  

For more details on configuring vLLM, refer to the [official documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html). After starting the server, update your config file accordingly. For step-by-step configuration instructions, see the [config modification guide](#modify-config). 

## Modify Config

The configuration file is located in the `config/` directory. This file allows you to set various parameters for the model, including prompts for each stage of processing. Below is an example configuration:

```yaml
# Core LLM Configuration (for self-hosted Parallel Processing Backend)
llm:
  name_or_path: your/model/path      # Local HuggingFace model directory
  url: http://localhost:5002/infer   # Local inference endpoint

# OpenAI-compatible API Settings
openai_api:
  model: model_name                  # API model identifier
  name_or_path: your/model/path      # Local HuggingFace model directory
  base_url: https://api.openai.com/v1  # for vLLM: http://<host>:<port>/v1/
  api_key: sk-xxxx                  
  is_vllm_sever: false              # Set true for vLLM servers

# Execution Parameters
max_work_count: 4                   # Max parallel workers/requests
use_openai_api: true                # Whether to use OpenAI API (including OpenAI-compatible APIs)

# Prompts
map_prompt: MAP_PROMPT              # Map stage prompt
collapse_prompt: COLLAPSE_PROMPT    # Collapse stage prompt
reduce_prompt: REDUCE_PROMPT        # Reduce stage prompt
```

### Configuration Fields

#### LLM Backend (`use_openai_api: false`)
- `llm.name_or_path`: Local model directory path (must match `hf-model-name` in backend)
- `llm.url`: The endpoint for the inference service. The default port is `5002`, which should align with the `port` specified in the backend.


#### OpenAI API (`use_openai_api: true`)
Supports both OpenAI and self-hosted OpenAI-compatible APIs (e.g., vLLM).
- `openai_api.model`: Model identifier for API calls
- `openai_api.name_or_path`: Local model directory (used for vLLM-based deployments)
- `openai_api.base_url`: API endpoint URL (When using vLLM, ensure the `base_url` matches the vLLM server configuration)
- `openai_api.api_key`: Authentication key
- `openai_api.is_vllm_sever`: Set `true` if using a self-hosted vLLM OpenAI-compatible API.

#### Execution Parameters
- `max_work_count`: use in concurrency control:  
  - Self-hosted: Matches backend `worker_num`  
  - API mode: Limits parallel requests (can be increased for higher concurrency).
- `use_openai_api`
  - `true`: OpenAI-compatible API  
  - `false`: Local inference service

### Deployment Guide  
- **Local Inference**: Ensure `llm.name_or_path` and backend service are aligned  
- **API Integration**: Configure `base_url` for OpenAI-compatible APIs (e.g., vLLM, OpenAI), set `is_vllm_server: true` if using a self-hosted API, and set `use_openai_api: true` to enable API mode.

Adjust these parameters according to your deployment environment. The `use_openai_api` flag determines active configuration groups(`true` enables OpenAI API, including OpenAI-compatible APIs like vLLM), while `max_work_count` governs parallel processing capacity.

## Running Inference on Your Data

You can quickly test the framework on your own data using the following script:

```python
from utils import read_yaml
from pipeline import BasePipeline

# Modify the configuration file path. The example configuration file is located in the `config/` directory.
map_reduce_config = read_yaml('/path/to/your/config.yaml')

# Define your context and question
context = 'your context'
question = 'your question'
chunk_size = 4096  # Adjust the chunk size as needed for your data

# Initialize the pipeline with the configuration
pipeline = BasePipeline(map_reduce_config)

# Run the pipeline
result = pipeline.run(doc=context, question=question, chunk_size=chunk_size)

# Print the result
print('===============Final Result===============\n')
print(result)
```

### Steps:
1. Modify `/path/to/your/config.yaml` to point to your configuration file. Refer to the [Modify Config](#modify-config) section for more details on the configuration.
2. Replace `context` and `question` with your input data.  
   - `context`: Input the text or document you want to analyze.  
   - `question`: Specify the query you want to answer based on the context.
3. Adjust `chunk_size` based on the length of your text.

This script allows you to test the framework on your own data before proceeding to large-scale evaluations.


# 📃 Evaluation


We provide scripts to evaluate our framework using [InfiniteBench](https://github.com/OpenBMB/InfiniteBench) in the `scripts/` directory. Follow the steps below to set up the evaluation:

## 1. Download the Dataset
Before running the evaluation, you need to download the InfiniteBench dataset. Refer to the [InfiniteBench](https://github.com/OpenBMB/InfiniteBench) repository for detailed instructions on how to obtain the dataset. Once downloaded, note the directory where the dataset is stored. We recommend storing the dataset in the data/ directory, which is the default directory used in the provided scripts.

## 2. Modify the Evaluation Script

We provide evaluation scripts in the `scripts/` directory. Here's an example script for evaluating the **En.MC** task:

```bash
output_dir='output/path'  #output path
task='longbook_choice_eng'
data_dir='your/data/dir'
mkdir ${output_dir}


export TOKENIZERS_PARALLELISM=false
python -u eval/infinitebench/eval_infinitebench_MR.py \
    --task=${task} \
    --output_dir=${output_dir} \
    --data_dir=${data_dir} \
    --config_file='config/qa.yaml' 

python -u eval/infinitebench/process_answer.py \
    --result_dir=${output_dir}

python eval/infinitebench/compute_scores.py \
    --task=${task} \
    --output_dir=${output_dir}/'processed' \

```

You can modify the following parameters as needed:
- **task**: Set the task you want to evaluate.
- **data_dir**: Specify the directory where the dataset is stored. Make sure this points to the correct path for the downloaded dataset.
- **output_dir**: Set the directory where the evaluation results will be saved.
- **config**: Define the path to your model configuration file. The prompts and settings in the config we provide are already properly aligned with the task, so no further changes should be necessary unless you have specific requirements.

Additionally, modify the 7th line of `eval/infinitebench/eval_infinitebench_MR.py`

```python
sys.path.append('/path/to/the/project')
```

Replace `/path/to/the/project` with the root directory of your project.

## 3. Run the Evaluation

After modifying the script, run it to evaluate the performance of your framework. The results will be saved in the specified `output_dir`. Since the output is in a structured format, you can find the extracted answers in `output_dir/processed` after running the scripts.



# 📊 Experiment Results

Our experiments demonstrate the improved performance of various LLMs using the $\text{LLM}\times\text{MapReduce}$ framework on InfiniteBench tasks. Detailed results are provided below.

|                               | Context length| Qwen2-70b | Kimi-Chat(2024.06) | GPT-4 (From InfiniteBench) | MiniCPM 3.0 x MR | Qwen2-70b x MR | Llama3-70bx MR |
| ----------------------------- | ---------- | --------- | ------------------ | -------------------------- | --------------- | ------------ | ------------- |
| Math.Find                     | 87.9k      | 59.71%    | 18.57%             | 60.00%                     | 83.43%          | 54.29%       | **91.43%**        |
| Retrieve.KV                   | 89.9k      | 29.00%    | 69.20%             | 89.00%                     | 93.80%          | 98.80%       | **98.89%**        |
| En.Dia                        | 103.6K     | 23.00%    | 23.00%             | 7.50%                      | 12.50%          | **46.50%**       | 17.50%        |
| Code.Debug                    | 114.7k     | 45.43%    | 38.32%             | 54.31%                     | 25.63%          | 54.82%       | **62.94%**       |
| Retrieve.Number               | 122.4k     | **100.00%**  | 97.45%             | **100.00%**                   | 99.32%          | **100.00%**     | 99.79%        |
| Retrieve.PassKey              | 122.4k     | **100.00%**   | 99.32%             | **100.00%**                   | 98.81%          | **100.00%**     | **100.00%**      |
| En.Sum                        | 171.5K     | 31.85%    | 29.94%             | 14.73%                     | 25.89%          | **32.39%**       | 30.63%        |
| En.MC                         | 184.4k     | 81.66%    | 79.91%             | 68.12%                     | 66.38%          |**83.84%**      | 82.10%        |
| En.QA        | 192.6k     | 21.97%    | 18.80%             | 22.44%                     | 28.39%          | 23.13%       | **34.70%**      |
| Zh.QA        | 2068.6k    | 21.40%    | 19.84%             | **25.96%**                    | 23.66%          | 19.10%       | N/A           |
| avg w/o Zh.QA | /          | 51.92%    | 52.96%             | 55.33%                     | 59.29%          | 64.98%       | **68.64%**        |
| avg                           | /          | 48.86%    | 49.65%             | 52.39%                     | 55.55%          | **60.39%**       | N/A           |

# 📝 Citation

```
@misc{zhou2024llmtimesmapreducesimplifiedlongsequenceprocessing,
      title={LLM$\times$MapReduce: Simplified Long-Sequence Processing using Large Language Models}, 
      author={Zihan Zhou and Chong Li and Xinyi Chen and Shuo Wang and Yu Chao and Zhili Li and Haoyu Wang and Rongqiao An and Qi Shi and Zhixing Tan and Xu Han and Xiaodong Shi and Zhiyuan Liu and Maosong Sun},
      year={2024},
      eprint={2410.09342},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2410.09342}, 
}
```



