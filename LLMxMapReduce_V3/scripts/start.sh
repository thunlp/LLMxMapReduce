#!/bin/bash
cd LLMxMapReduce_V3
if [ $# -lt 1 ]; then
    echo "Usage: $0 <topic> [description]"
    exit 1
fi
export PYTHONPATH=$(pwd):${PYTHONPATH}
TOPIC="$1"
DESCRIPTION="$2"
DATE=$(date +%Y%m%d)
source venv/bin/activate
if [ -n "$DESCRIPTION" ]; then
    python run_llm_analyse.py "$TOPIC" "$DESCRIPTION"
else
    python run_llm_analyse.py "$TOPIC"
fi
uv run src/start_pipeline.py \
    --input_file output/${DATE}/${TOPIC}/search/crawl_results_${TOPIC}.json \
    --config_file config/unified_config.json \
    --output_file output/${DATE}/${TOPIC}/${TOPIC}.json \