#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  echo "[FAIL] .venv가 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi

source "${ROOT_DIR}/.venv/bin/activate"
source /opt/ros/humble/setup.bash

if [[ ! -f "${ROOT_DIR}/ros2_ws/install/setup.bash" ]]; then
  echo "[FAIL] ROS workspace가 아직 build되지 않았습니다." >&2
  echo "       먼저 터미널 1에서 scripts/run_robot_interaction_logs.sh를 실행하세요." >&2
  exit 1
fi

source "${ROOT_DIR}/ros2_ws/install/setup.bash"

exec python3 "${ROOT_DIR}/scripts/robot_interaction_simple_terminal.py"
