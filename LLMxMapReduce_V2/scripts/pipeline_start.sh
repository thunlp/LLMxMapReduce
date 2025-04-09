export PYTHONPATH=$(pwd):${PYTHONPATH}

topic=$1
output_file_path=$2
log_dir="./output/log"

mkdir -p $log_dir

log_file="${log_dir}/${timestamp}_$(basename "$output_file_path").log"
  # --topic "Multi Modal LLM" \
python ./src/start_pipeline.py \
  --input_file "output/recp_3_layer_6_bestof_3_refinecount_3_20_20250211_001804_block_1.jsonl" \
  --output_file output/fig_data.json \
  --config_file ./config/model_config.json\
  --block_count 0\
  --data_num 1\
  2>&1 | tee "$log_file"