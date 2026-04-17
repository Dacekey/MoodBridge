#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Launching MoodBridge demo conversation..."

cd "$PROJECT_ROOT"

source ~/anaconda3/etc/profile.d/conda.sh
conda activate mood_bridge
source "$PROJECT_ROOT/../env/llm.sh"
cd ..
python -m demos.demo_conversation
