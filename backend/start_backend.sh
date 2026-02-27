#!/bin/bash
# Simple backend starter — no Whisper required (app handles transcription internally)
# Usage: ./start_backend.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "ERROR: venv not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Kill any existing process on port 5167
if lsof -i :5167 | grep -q LISTEN; then
    echo "Killing existing process on port 5167..."
    kill -9 $(lsof -t -i :5167) 2>/dev/null
    sleep 1
fi

echo "Starting Meetily backend on http://localhost:5167 ..."
echo "API docs: http://localhost:5167/docs"
echo "Press Ctrl+C to stop."
echo ""

source venv/bin/activate
cd app
python main.py
