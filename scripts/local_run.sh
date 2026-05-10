#!/bin/bash

set -e

mode=""
node=""
input=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${COZE_WORKSPACE_PATH:-$(dirname "$SCRIPT_DIR")}"

usage() {
  echo "Usage: $0 -m <mode> [-n <node_id>] [-i <input_json>]"
  echo ""
  echo "Options:"
  echo "  -m <mode>        Run mode: http, flow, node, agent"
  echo "  -n <node_id>     Node ID (required for node mode only)"
  echo "  -i <input_json>  Input data, supports JSON string or plain text"
  echo "  -h               Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 -m flow"
  echo "  $0 -m flow -i '{\"text\": \"Hello\"}'"
  echo "  $0 -m flow -i 'Hello'"
  echo "  $0 -m node -n node_1 -i '{\"text\": \"test\"}'"
}

while getopts "m:n:i:h" opt; do
  case "$opt" in
    m)
      mode="$OPTARG"
      ;;
    n)
      node="$OPTARG"
      ;;
    i)
      input="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "Invalid option: -$OPTARG"
      usage
      exit -1
      ;;
  esac
done

if [ -z "$mode" ]; then
  echo "Error: Mode is required"
  usage
  exit 1
fi

cd "$WORK_DIR"

case "$mode" in
  http)
    echo "Starting HTTP server..."
    exec python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
    ;;
  flow|node|agent)
    echo "Running in $mode mode..."
    if [ "$mode" = "node" ] && [ -z "$node" ]; then
      echo "Error: Node ID is required for node mode"
      exit 1
    fi
    exec python -m src.main "$mode" ${node:+-n "$node"} ${input:+-i "$input"}
    ;;
  *)
    echo "Error: Unknown mode '$mode'"
    usage
    exit 1
    ;;
esac
