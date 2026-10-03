#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SPLIT="${SPLIT:-validation}"

if [[ "$SPLIT" != "validation" && "$SPLIT" != "test" ]]; then
  echo "SPLIT must be validation or test" >&2
  exit 2
fi

if [[ "$SPLIT" == "test" ]]; then
  echo "WARNING: fixed test 1,507 rows will be evaluated. Do not use test results for tuning." >&2
fi

exec "$PYTHON_BIN" experiments/tod_slm/training/evaluate.py \
  --config "$CONFIG" \
  --split "$SPLIT" \
  "$@"
