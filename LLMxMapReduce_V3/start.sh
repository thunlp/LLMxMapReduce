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
source .venv/bin/activate
if [ -n "$DESCRIPTION" ]; then
    uv run python -m src.start "$TOPIC" "$DESCRIPTION"
else
    uv run python -m src.start "$TOPIC"
fi