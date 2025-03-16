output_dir='output/path'  #output path
task='longbook_sum_eng'
data_dir='your/data/dir'
mkdir ${output_dir}


export TOKENIZERS_PARALLELISM=false
python -u eval/infinitebench/eval_infinitebench_MR.py \
    --task=${task} \
    --output_dir=${output_dir} \
    --data_dir=${data_dir} \
    --config_file='config/sum.yaml' 

python -u eval/infinitebench/process_answer.py \
    --result_dir=${output_dir}

python eval/infinitebench/compute_scores.py \
    --task=${task} \
    --output_dir=${output_dir}/'processed' \