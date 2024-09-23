#!/bin/bash

# Initializing variables
HF_MODEL_NAME="your/model/path"
PER_PROC_GPUS=1 # The number of GPUs occupied by each child process. By default, all are occupied, and it is a single process. This value must be divisible by the total number of available GPUs in the POD. The number of workers = the total number of GPUs / this value
CUDA_VISIBLE_DEVICES="0,1,2,6"
PORT=5002 # Default port
INFER_TYPE="vLLM" # The default inference type is "vLLM" or "transformers". The latter uses transformers for model deployment inference.
QUANTIZATION=awq
TIMEOUT=6000 # Default timeout
MAX_MODEL_LEN=None # The maximum length of the model
# Parsing long options
options=$(getopt -o "" --long hf-model-name:,per-proc-gpus:,cuda-visible-devices:,port:,infer-type:,quantization:,max-model-len: -- "$@")

# Set the parsed parameters
eval set -- "$options"

# Iterate over parsed options and arguments
while true; do
    case $1 in
        --hf-model-name)
            HF_MODEL_NAME=$2
            shift 2
            ;;
        --per-proc-gpus)
            PER_PROC_GPUS=$2 
            shift 2
            ;;
        --cuda-visible-devices)
            CUDA_VISIBLE_DEVICES=$2
            shift 2
            ;;
        --port)
            PORT=$2
            shift 2
            ;;
        --infer-type)
            INFER_TYPE=$2
            shift 2
            ;;
        --quantization)
            QUANTIZATION=$2
            shift 2
            ;;
        --max-model-len)
            MAX_MODEL_LEN=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
    esac
done

# Checks if the required HF_MODEL_NAME is provided
if [ -z "$HF_MODEL_NAME" ]; then
  echo "Error: You must provide HF_MODEL_NAME using --hf-model-name."
  exit 1
fi

# Exporting environment variables
export PER_PROC_GPUS
export HF_MODEL_NAME
export CUDA_VISIBLE_DEVICES
export PORT
export INFER_TYPE
export QUANTIZATION
export MAX_MODEL_LEN

# run gunicorn
gunicorn -c URLs/gunicorn_conf.py
