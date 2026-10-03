#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"

# ROS setup scripts may reference optional variables that are unset.
set +u
source /opt/ros/humble/setup.bash
source "${ROOT_DIR}/ros2_ws/install/setup.bash"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/.venv/bin/activate"
fi

cd "${ROOT_DIR}"
exec python -m uvicorn api.web_main:app --host "${HOST}" --port "${PORT}"
