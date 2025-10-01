#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC_PATH="$PROJECT_ROOT/src"
export PYTHONPATH="$SRC_PATH"
echo "Running sellmanagement with PYTHONPATH=$PYTHONPATH"
python -m sellmanagement "$@"


