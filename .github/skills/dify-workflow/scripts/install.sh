#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="${1:-.}"

cd "$PROJECT_PATH"
python -m pip install -e .
python -m pip show dify-ai-workflow-tools
