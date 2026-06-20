#!/bin/bash
# Launch endgame-ai server from WSL2
# Access at http://localhost:9077 from Windows browser
cd "$(dirname "$0")"
echo "endgame-ai server starting on 0.0.0.0:9077"
echo "Open http://localhost:9077 in Chrome"
python3 server.py "$@"
