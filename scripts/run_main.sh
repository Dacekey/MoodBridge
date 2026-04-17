#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Launching MoodBridge main app..."

gnome-terminal --title="MoodBridge Backend" -- bash -c "
cd \"$PROJECT_ROOT/../backend\"
source ~/anaconda3/etc/profile.d/conda.sh
conda activate mood_bridge
source \"$PROJECT_ROOT/../env/llm.sh\"

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --ws-ping-interval 60 \
  --ws-ping-timeout 60 \
  --timeout-keep-alive 120

exec bash
"

sleep 2

gnome-terminal --title="MoodBridge Frontend" -- bash -c "
cd \"$PROJECT_ROOT/../frontend\"
source \"$PROJECT_ROOT/../env/llm.sh\"

npm run dev

exec bash
"

echo "MoodBridge backend + frontend launched."
