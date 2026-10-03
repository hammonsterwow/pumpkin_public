#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Fail early if the configured max_length cannot contain every row.
"$PYTHON_BIN" experiments/tod_slm/training/inspect_token_lengths.py \
  --config "$CONFIG"

# Single GPU: run this script normally.
# Multi GPU: set USE_ACCELERATE=1 and expose only the GPUs to be used.
# Example for the school TITAN Xp server:
#   CUDA_VISIBLE_DEVICES=1,2,3 USE_ACCELERATE=1 NUM_PROCESSES=3 \
#     bash scripts/train_tod_qwen_lora.sh
if [[ "${USE_ACCELERATE:-0}" == "1" ]]; then
  NUM_PROCESSES="${NUM_PROCESSES:-3}"
  MIXED_PRECISION="${MIXED_PRECISION:-fp16}"
  exec accelerate launch \
    --multi_gpu \
    --num_processes "$NUM_PROCESSES" \
    --num_machines 1 \
    --mixed_precision "$MIXED_PRECISION" \
    --dynamo_backend no \
    experiments/tod_slm/training/train_lora.py \
    --config "$CONFIG" \
    "$@"
fi

exec "$PYTHON_BIN" experiments/tod_slm/training/train_lora.py \
  --config "$CONFIG" \
  "$@"
