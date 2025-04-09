# modify the LD_LIBRARY_PATH to your actual python environmental path
export LD_LIBRARY_PATH=${HOME}/anaconda3/envs/YOUR_ENV_NAME/lib/YOUR_PYTHON_VERSION/site-packages/nvidia/nvjitlink/lib:${LD_LIBRARY_PATH}
export PYTHONPATH=$(pwd):${PYTHONPATH}


current_datetime=$(date +%Y%m%d_%H%M%S)
jsonl_file=$1

echo "start to eval"
echo "logging to ./output/eval/log/${current_datetime}_eval_survey.log"

mkdir -p ./output/eval/log
sleep 1
python ./evaluation/all_eval.py \
    --jsonl_file $jsonl_file \
    --saving_path ./output/eval/${current_datetime} \
    --eval_model  gemini-2.0-flash-thinking-exp-1219 \
    --infer_type OpenAI \
    --method_name LLMxMRv2  \
     2>&1 | tee ./output/eval/log/${current_datetime}_eval_survey.log