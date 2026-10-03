#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 experiments/tod_slm/review/app.py \
  --input data/tod/pumpkin_tod_v1_review_sample.jsonl \
  "$@"
