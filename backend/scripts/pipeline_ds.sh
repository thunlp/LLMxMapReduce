export PYTHONPATH=$(pwd):${PYTHONPATH}
# export PROMPT_LANGUAGE="zh"
export OPENAI_API_KEY="7891b3e1-51cf-4979-9eae-ecdf4e411d5e"
# another api key (enterprice) 7891b3e1-51cf-4979-9eae-ecdf4e411d5e, model name: ep-20250513174726-q2tj5
export OPENAI_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
# export SERP_API_KEY="1dada74f8fcd48b9d5072097b8362e8f2811b2ecc6fe7f52a57a972e0555b42c"
export SERPER_API_KEY="769aed5f5ca7b1ad747d71b57224eb53135d0069"
# for linux proxy
export all_proxy="http://192.168.128.1:7890/"

topic=$1
output_file_path=$2
log_dir="./output/log"
timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p $log_dir

log_file="${log_dir}/${timestamp}_$(basename "$output_file_path").log"
python ./src/start_pipeline.py \
  --topic "${topic}" \
  --output_file ${output_file_path} \
  --config_file ./config/model_config_ds.json \
  --block_count 1\
  --data_num 1\
  --search_model "ep-20250513174726-q2tj5" \
  2>&1 | tee "$log_file"
