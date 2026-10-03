#!/usr/bin/env bash
set -eo pipefail
set +u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
NLU_PYTHON_BIN="${PUMPKIN_NLU_PYTHON:-${ROOT_DIR}/.venv-nlu/bin/python}"

if [[ ! -x "${NLU_PYTHON_BIN}" ]]; then
  echo "NLU 가상환경 Python을 찾을 수 없습니다: ${NLU_PYTHON_BIN}" >&2
  exit 1
fi

# PyTorch wheel과 시스템 Torch 공유 라이브러리가 섞이지 않도록 기존 값을 제거한다.
unset LD_LIBRARY_PATH
export PYTHONNOUSERSITE=1
export PUMPKIN_PROJECT_ROOT="${PUMPKIN_PROJECT_ROOT:-${ROOT_DIR}}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-cuda}"

# LD_LIBRARY_PATH를 비운 뒤 ROS2가 필요한 라이브러리 경로만 다시 구성한다.
source /opt/ros/humble/setup.bash
source "${WORKSPACE}/install/setup.bash"

# 실행 전에 rclpy와 CUDA PyTorch를 같은 환경에서 함께 불러올 수 있는지 확인한다.
"${NLU_PYTHON_BIN}" - <<'PY'
import rclpy
import torch

if not torch.cuda.is_available():
    raise SystemExit("NLU 가상환경 PyTorch에서 CUDA GPU를 찾지 못했습니다.")
PY

exec "${NLU_PYTHON_BIN}" -m robot_controller.nlu_node "$@"
