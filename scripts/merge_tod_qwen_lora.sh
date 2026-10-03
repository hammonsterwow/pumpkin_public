#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" experiments/tod_slm/training/merge_lora.py \
  --config "$CONFIG" \
  "$@"
