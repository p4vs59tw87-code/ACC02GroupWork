#!/bin/bash

# Load project environment variables
# Usage: source ./load_env.sh or . ./load_env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

eval $(python3 "$SCRIPT_DIR/load_env.py")
