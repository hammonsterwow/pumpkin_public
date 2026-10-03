#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${REPO_ROOT}/nlu/saved_models/structure_b_item_query_decoder"

cd "${REPO_ROOT}"

echo "=== Jetson system ==="
uname -a
if [[ -f /etc/nv_tegra_release ]]; then
  cat /etc/nv_tegra_release
fi
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query --show nvidia-jetpack 2>/dev/null || true
fi

echo
echo "=== Python environment ==="
python3 --version
python3 - <<'PY'
import platform

print("machine:", platform.machine())

try:
    import torch
    print("torch:", torch.__version__)
    print("cuda_available:", torch.cuda.is_available())
    print("torch_cuda:", torch.version.cuda)
    if torch.cuda.is_available():
        print("gpu:", torch.cuda.get_device_name(0))
except Exception as error:
    print("torch_error:", repr(error))
    raise SystemExit(2)

try:
    import transformers
    print("transformers:", transformers.__version__)
except Exception as error:
    print("transformers_error:", repr(error))
    raise SystemExit(3)
PY

echo
echo "=== Model files ==="
for required in \
  "${MODEL_DIR}/best_model.pt" \
  "${MODEL_DIR}/tokenizer"; do
  if [[ ! -e "${required}" ]]; then
    echo "Missing: ${required}" >&2
    exit 4
  fi
done

ls -lh "${MODEL_DIR}/best_model.pt"
find "${MODEL_DIR}/tokenizer" -maxdepth 1 -type f -print | sort

echo
echo "=== NLU smoke test ==="
python3 -m nlu.cli \
  "아이스 카페라떼 두 잔 주세요" \
  --model-dir "${MODEL_DIR}" \
  --device auto
