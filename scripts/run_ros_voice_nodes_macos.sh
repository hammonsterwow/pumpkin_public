#!/usr/bin/env bash
set -eo pipefail
set +u

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "이 스크립트는 macOS 전용입니다." >&2
  exit 1
fi

# Pixi can inherit Anaconda/Homebrew Python and OpenSSL variables from the
# parent shell. Those variables can make Pixi Python load /opt/anaconda3
# libraries and fail with missing OpenSSL symbols.
unset PYTHONHOME
unset PYTHONPATH
unset DYLD_LIBRARY_PATH
unset DYLD_FALLBACK_LIBRARY_PATH

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
PYTHON_BIN="${PUMPKIN_PYTHON:-$(command -v python3 || true)}"
LOG_DIR="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}"
NLU_READY_FILE="/tmp/pumpkin_nlu_ready"
STARTUP_TIMEOUT="${PUMPKIN_STARTUP_TIMEOUT:-300}"
ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-0}"

if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "Python을 찾을 수 없습니다. 먼저 Pumpkin Pixi 환경을 실행하세요." >&2
  echo "예: pixi shell" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import rclpy
import torch
import transformers
PY
then
  echo "현재 Python 환경에 ROS2/PyTorch 의존성이 없습니다." >&2
  echo "저장소 루트에서 'pixi install'을 실행하세요." >&2
  exit 1
fi

if [[ ! -f "${WORKSPACE}/install/setup.bash" ]]; then
  echo "ROS2 workspace가 빌드되지 않았습니다." >&2
  echo "다음 명령을 먼저 실행하세요:" >&2
  echo "  cd ${ROOT_DIR}" >&2
  echo "  pixi run build-ros" >&2
  exit 1
fi

source "${WORKSPACE}/install/setup.bash"

export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export PUMPKIN_NLU_DEVICE="cpu"

mkdir -p "${LOG_DIR}"
rm -f "${LOG_DIR}"/*.log "${NLU_READY_FILE}"

PID_NAMES=()
PID_VALUES=()
LOG_FILES=()

find_index() {
  local target="$1"
  local i
  for ((i = 0; i < ${#PID_NAMES[@]}; i++)); do
    if [[ "${PID_NAMES[$i]}" == "${target}" ]]; then
      echo "${i}"
      return 0
    fi
  done
  return 1
}

print_log_tail() {
  local name="$1"
  local index
  index="$(find_index "${name}" || true)"
  local log_file="${LOG_DIR}/${name}.log"
  if [[ -n "${index}" ]]; then
    log_file="${LOG_FILES[$index]}"
  fi

  echo
  echo "========== ${name} 마지막 로그 =========="
  if [[ -f "${log_file}" ]]; then
    tail -n 100 "${log_file}"
  else
    echo "로그 파일이 없습니다: ${log_file}"
  fi
  echo "========================================="
}

start_process() {
  local name="$1"
  shift
  local log_file="${LOG_DIR}/${name}.log"

  echo "[START] ${name}"
  "$@" > >(tee -a "${log_file}") 2>&1 &
  PID_NAMES+=("${name}")
  PID_VALUES+=("$!")
  LOG_FILES+=("${log_file}")
}

assert_alive() {
  local name="$1"
  local index
  index="$(find_index "${name}")"
  local pid="${PID_VALUES[$index]}"

  if kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi

  set +e
  wait "${pid}"
  local status=$?
  set -e
  echo "[FAIL] ${name} 프로세스가 종료되었습니다. exit=${status}" >&2
  print_log_tail "${name}"
  return 1
}

wait_for_ready_file() {
  local name="$1"
  local ready_file="$2"
  local timeout_seconds="$3"
  local elapsed=0

  echo "[WAIT] ${name} 준비 대기 중... 최대 ${timeout_seconds}초"
  while ((elapsed < timeout_seconds)); do
    if [[ -f "${ready_file}" ]]; then
      echo "[READY] ${name}"
      cat "${ready_file}"
      return 0
    fi
    assert_alive "${name}" || return 1
    sleep 1
    elapsed=$((elapsed + 1))
  done

  echo "[FAIL] ${name} 준비 시간이 초과되었습니다." >&2
  print_log_tail "${name}"
  return 1
}

cleanup() {
  echo
  echo "Stopping pumpkin ROS nodes..."
  local pid
  for pid in "${PID_VALUES[@]}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  rm -f "${NLU_READY_FILE}"
}
trap cleanup EXIT INT TERM

"${PYTHON_BIN}" - <<'PY'
import rclpy
import robot_controller
import torch

print("macOS Pumpkin text-test environment OK")
print("Python/ROS package:", robot_controller.__file__)
print("PyTorch:", torch.__version__)
PY

echo
echo "Starting Pumpkin ROS text-test pipeline on macOS..."
echo "project=${ROOT_DIR}"
echo "python=${PYTHON_BIN}"
echo "nlu=cpu"
echo "stt=disabled (macOS native audio stack is not used)"
echo "tts=disabled (Jetson TTS code is not used or modified)"
echo "logs=${LOG_DIR}"

start_process decision_node "${PYTHON_BIN}" -m robot_controller.decision_node_order_handoff
start_process response_manager_node "${PYTHON_BIN}" -m robot_controller.response_manager_node
start_process action_node "${PYTHON_BIN}" -m robot_controller.action_node_order_handoff

if [[ "${ENABLE_VISION}" == "1" ]]; then
  start_process vision_node "${PYTHON_BIN}" -m robot_controller.vision_node
else
  echo "vision_node disabled (set PUMPKIN_ENABLE_VISION=1 to enable)"
fi

sleep 2
for node in decision_node response_manager_node action_node; do
  assert_alive "${node}"
done

start_process nlu_node "${PYTHON_BIN}" -m robot_controller.nlu_node
wait_for_ready_file nlu_node "${NLU_READY_FILE}" "${STARTUP_TIMEOUT}"

echo
echo "Pumpkin ROS text-test pipeline is READY on macOS (STT/TTS disabled)."
echo "다른 터미널에서: pixi run terminal-chat"
echo "디버그: pixi run terminal-chat-debug"
echo "Press Ctrl+C to stop all nodes."
echo

while true; do
  for ((i = 0; i < ${#PID_VALUES[@]}; i++)); do
    pid="${PID_VALUES[$i]}"
    if ! kill -0 "${pid}" 2>/dev/null; then
      set +e
      wait "${pid}"
      status=$?
      set -e
      name="${PID_NAMES[$i]}"
      echo "[FAIL] ${name} 프로세스가 종료되었습니다. exit=${status}" >&2
      print_log_tail "${name}"
      exit "${status}"
    fi
  done
  sleep 1
done
