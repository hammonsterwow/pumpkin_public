#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  echo "[FAIL] .venv가 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${ROOT_DIR}/.venv/bin/activate"

export PYTHONNOUSERSITE=1
export PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/ros2_ws/src/robot_controller:${PYTHONPATH:-}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

python -m compileall -q ros2_ws/src/robot_controller/robot_controller

pytest -q \
  ros2_ws/src/robot_controller/test/test_hand_quantity_recognizer.py \
  ros2_ws/src/robot_controller/test/test_hand_quantity_gesture_flow.py \
  ros2_ws/src/robot_controller/test/test_multimodal_gesture_flow.py
