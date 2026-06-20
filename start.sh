#!/bin/bash
# Launch endgame-ai on Windows Python (required for desktop access)
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
echo "endgame-ai slot 1 → http://localhost:9078"
python server.py "$@"
