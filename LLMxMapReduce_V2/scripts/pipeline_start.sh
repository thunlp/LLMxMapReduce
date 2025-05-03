export PYTHONPATH=$(pwd):${PYTHONPATH}

topic=$1
output_file_path=$2
log_dir="./output/log"
timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p $log_dir

log_file="${log_dir}/${timestamp}_$(basename "$output_file_path").log"
python ./src/start_pipeline.py \
  --topic ${topic} \
  --output_file ${output_file_path} \
  --config_file ./config/model_config.json\
  --block_count 1\
  --data_num 1\
  2>&1 | tee "$log_file"
