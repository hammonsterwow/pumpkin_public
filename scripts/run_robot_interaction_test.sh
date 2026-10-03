#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_SCRIPT="${ROOT_DIR}/scripts/run_robot_interaction_demo.sh"
MONITOR_SCRIPT="${ROOT_DIR}/scripts/robot_interaction_terminal.py"
LOG_DIR="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}"
LAUNCHER_LOG="${LOG_DIR}/robot_interaction_demo.log"
DEMO_PID=""
MONITOR_PID=""

cleanup() {
  local status=$?
  if [[ -n "${MONITOR_PID}" ]] && kill -0 "${MONITOR_PID}" 2>/dev/null; then
    kill "${MONITOR_PID}" 2>/dev/null || true
  fi
  if [[ -n "${DEMO_PID}" ]] && kill -0 "${DEMO_PID}" 2>/dev/null; then
    kill "${DEMO_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT INT TERM

if [[ ! -f "${DEMO_SCRIPT}" ]]; then
  echo "[FAIL] ${DEMO_SCRIPT} 를 찾을 수 없습니다." >&2
  exit 1
fi
if [[ ! -f "${MONITOR_SCRIPT}" ]]; then
  echo "[FAIL] ${MONITOR_SCRIPT} 를 찾을 수 없습니다." >&2
  exit 1
fi

cd "${ROOT_DIR}"
mkdir -p "${LOG_DIR}"
: > "${LAUNCHER_LOG}"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.venv/bin/activate"
else
  echo "[FAIL] .venv 가 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi

# ROS setup scripts may reference variables before defining them. Do not run
# this launcher with bash nounset (-u); the project launchers intentionally use
# the same ROS-compatible behavior.
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
if [[ -f "${ROOT_DIR}/ros2_ws/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/ros2_ws/install/setup.bash"
fi

export PUMPKIN_ENABLE_TEGRASTATS="${PUMPKIN_ENABLE_TEGRASTATS:-0}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-cuda}"
export PUMPKIN_ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-1}"
export PUMPKIN_ENABLE_FACE_DISPLAY="${PUMPKIN_ENABLE_FACE_DISPLAY:-1}"
export PUMPKIN_MOTOR_BACKEND="${PUMPKIN_MOTOR_BACKEND:-pca9685}"

echo "============================================================"
echo " Pumpkin 실제 로봇 주문 통합 테스트 - ONE COMMAND"
echo "============================================================"
echo "이 명령 하나가 다음을 모두 실행합니다."
echo "  Camera / 사람 감지 / NOD-SHAKE"
echo "  VAD / Faster-Whisper STT / NLU / FSM"
echo "  TTS speaker / 얼굴 LCD / PCA9685 목 servo"
echo "  터미널 통합 모니터"
echo ""
echo "launcher log: ${LAUNCHER_LOG}"
echo "============================================================"
echo

echo "[START] 실제 로봇 ROS 파이프라인을 시작합니다."
# Show startup output live while also retaining the complete launcher log.
# This is important because dependency/build/CUDA failures can happen before
# vision_node.log or any ROS topic exists.
bash "${DEMO_SCRIPT}" > >(tee -a "${LAUNCHER_LOG}") 2>&1 &
DEMO_PID=$!

# Give build/dependency checks a moment to begin. If the launcher exits here,
# report it immediately instead of waiting for the ROS monitor timeout.
for _ in $(seq 1 10); do
  if ! kill -0 "${DEMO_PID}" 2>/dev/null; then
    set +e
    wait "${DEMO_PID}"
    DEMO_STATUS=$?
    set -e
    echo "[FAIL] 로봇 파이프라인이 시작 중 종료되었습니다. exit=${DEMO_STATUS}" >&2
    echo "[DEBUG] ${LAUNCHER_LOG} 마지막 로그" >&2
    tail -n 160 "${LAUNCHER_LOG}" >&2 || true
    exit "${DEMO_STATUS}"
  fi
  sleep 1
done

echo "[MONITOR] ROS 구성요소가 올라올 때까지 기다립니다."
echo "          준비가 완료되면 카메라 앞에 서세요."
echo

python3 "${MONITOR_SCRIPT}" \
  --ready-timeout "${PUMPKIN_INTERACTION_READY_TIMEOUT:-240}" &
MONITOR_PID=$!

# Supervise both processes. If the physical launcher dies, stop the monitor
# immediately and expose the real startup/runtime failure instead of showing
# only missing ROS topics for several minutes.
set +e
wait -n "${DEMO_PID}" "${MONITOR_PID}"
FIRST_STATUS=$?
set -e

if ! kill -0 "${DEMO_PID}" 2>/dev/null; then
  set +e
  wait "${DEMO_PID}" 2>/dev/null
  DEMO_STATUS=$?
  set -e
  echo
  echo "[FAIL] 실제 로봇 파이프라인이 종료되었습니다. exit=${DEMO_STATUS}"
  echo "------------------------------------------------------------"
  tail -n 200 "${LAUNCHER_LOG}" || true
  echo "------------------------------------------------------------"
  echo "전체 로그: ${LAUNCHER_LOG}"
  exit "${DEMO_STATUS}"
fi

if ! kill -0 "${MONITOR_PID}" 2>/dev/null; then
  set +e
  wait "${MONITOR_PID}" 2>/dev/null
  MONITOR_STATUS=$?
  set -e
  if [[ "${MONITOR_STATUS}" -ne 0 ]]; then
    echo
    echo "[DEBUG] 통합 모니터가 ROS 준비를 확인하지 못했습니다."
    echo "------------------------------------------------------------"
    tail -n 200 "${LAUNCHER_LOG}" || true
    echo "------------------------------------------------------------"
    echo "전체 로그: ${LAUNCHER_LOG}"
  fi
  exit "${MONITOR_STATUS}"
fi

exit "${FIRST_STATUS}"
