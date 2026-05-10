#!/bin/bash

set -e

WORK_DIR="${COZE_WORKSPACE_PATH:-.}"
PORT=8000

usage() {
  echo "Usage: $0 -p <port>"
}

while getopts "p:h" opt; do
  case "$opt" in
    p)
      PORT="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      usage
      exit 1
      ;;
  esac
done

cd "$WORK_DIR"

echo "Starting HTTP server on port $PORT..."
exec python -m uvicorn src.main:app --host 0.0.0.0 --port "$PORT"
