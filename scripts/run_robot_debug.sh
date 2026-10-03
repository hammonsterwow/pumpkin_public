#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RAW_LOG="${LOG_DIR}/demo_raw_${STAMP}.log"
DEBUG_LOG="${LOG_DIR}/demo_debug_${STAMP}.log"
LATEST_DEBUG="${LOG_DIR}/demo_debug_latest.log"
ROBOT_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  if [[ -n "${ROBOT_PID}" ]] && kill -0 "${ROBOT_PID}" 2>/dev/null; then
    kill -INT "${ROBOT_PID}" 2>/dev/null || true
  fi
  wait "${ROBOT_PID}" 2>/dev/null || true

  echo
  echo "[DEBUG] concise log: ${DEBUG_LOG}"
  echo "[DEBUG] raw log    : ${RAW_LOG}"
  exit "${status}"
}
trap cleanup EXIT INT TERM

mkdir -p "${LOG_DIR}"

if [[ ! -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  echo "[FAIL] .venv가 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi

cd "${ROOT_DIR}"
# shellcheck disable=SC1091
source "${ROOT_DIR}/.venv/bin/activate"
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
if [[ -f "${ROOT_DIR}/ros2_ws/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/ros2_ws/install/setup.bash"
fi

echo "============================================================"
echo " Pumpkin 시연 디버그 모드"
echo "============================================================"
echo "화면에는 핵심 진단 로그만 표시합니다."
echo "전체 ROS 출력은 ${RAW_LOG} 에 저장합니다."
echo "============================================================"
echo

bash "${ROOT_DIR}/scripts/run_robot_with_monitor.sh" >"${RAW_LOG}" 2>&1 &
ROBOT_PID=$!

sleep 2

set +e
python3 "${ROOT_DIR}/scripts/robot_interaction_debug_terminal.py"   --log-path "${DEBUG_LOG}"   2>&1 | tee "${DEBUG_LOG}"
DEBUG_STATUS=${PIPESTATUS[0]}
set -e

cp -f "${DEBUG_LOG}" "${LATEST_DEBUG}" 2>/dev/null || true

if ! kill -0 "${ROBOT_PID}" 2>/dev/null; then
  echo
  echo "[FAIL] 로봇 파이프라인이 먼저 종료되었습니다."
  echo "마지막 원본 로그:"
  tail -n 80 "${RAW_LOG}" || true
  exit 1
fi

exit "${DEBUG_STATUS}"
