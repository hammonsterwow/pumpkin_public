#!/usr/bin/env bash
set -eo pipefail
set +u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
ROS_SETUP="${PUMPKIN_ROS_SETUP:-/opt/ros/humble/setup.bash}"
CORE_PYTHON_BIN="${PUMPKIN_CORE_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
NLU_PYTHON_BIN="${PUMPKIN_NLU_PYTHON:-${ROOT_DIR}/.venv-nlu/bin/python}"
NLU_RUNNER="${ROOT_DIR}/scripts/run_nlu_node_cuda.sh"
LOG_DIR="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}"
NLU_READY_FILE="/tmp/pumpkin_nlu_ready"
STT_READY_FILE="/tmp/pumpkin_stt_ready"
STARTUP_TIMEOUT="${PUMPKIN_STARTUP_TIMEOUT:-240}"

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "ROS2 Humble setup을 찾을 수 없습니다: ${ROS_SETUP}" >&2
  echo "Ubuntu 22.04에 ROS2 Humble을 설치하거나 PUMPKIN_ROS_SETUP 경로를 지정하세요." >&2
  exit 1
fi
if [[ ! -f "${WORKSPACE}/install/setup.bash" ]]; then
  echo "ROS2 workspace가 빌드되지 않았습니다: ${WORKSPACE}/install/setup.bash" >&2
  echo "먼저: cd ${WORKSPACE} && source ${ROS_SETUP} && colcon build --symlink-install" >&2
  exit 1
fi
if [[ ! -x "${CORE_PYTHON_BIN}" ]]; then
  echo "코어/STT 가상환경 Python을 찾을 수 없습니다: ${CORE_PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -x "${NLU_PYTHON_BIN}" ]]; then
  echo "NLU 가상환경 Python을 찾을 수 없습니다: ${NLU_PYTHON_BIN}" >&2
  exit 1
fi

unset LD_LIBRARY_PATH
source "${ROS_SETUP}"
source "${WORKSPACE}/install/setup.bash"

export PYTHONNOUSERSITE=1
export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -S "${XDG_RUNTIME_DIR}/pulse/native" ]]; then
  export PULSE_SERVER="${PULSE_SERVER:-unix:${XDG_RUNTIME_DIR}/pulse/native}"
fi

# auto: 사용 가능한 CUDA를 먼저 확인하고, 없으면 CPU로 전환한다.
REQUESTED_DEVICE="${PUMPKIN_NLU_DEVICE:-auto}"
DEVICE_INFO="$(${NLU_PYTHON_BIN} - <<'PY'
import torch
print("cuda" if torch.cuda.is_available() else "cpu")
PY
)"

if [[ "${REQUESTED_DEVICE}" == "auto" ]]; then
  NLU_DEVICE="${DEVICE_INFO}"
elif [[ "${REQUESTED_DEVICE}" == "cuda" && "${DEVICE_INFO}" != "cuda" ]]; then
  echo "[WARN] CUDA를 요청했지만 PyTorch에서 GPU를 찾지 못해 CPU로 전환합니다." >&2
  NLU_DEVICE="cpu"
else
  NLU_DEVICE="${REQUESTED_DEVICE}"
fi
export PUMPKIN_NLU_DEVICE="${NLU_DEVICE}"

STT_DEVICE="${PUMPKIN_STT_DEVICE:-auto}"
if [[ "${STT_DEVICE}" == "auto" ]]; then
  STT_DEVICE="$(${CORE_PYTHON_BIN} - <<'PY'
import ctranslate2
print("cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu")
PY
)"
fi

if [[ "${STT_DEVICE}" == "cuda" ]]; then
  STT_COMPUTE_TYPE="${PUMPKIN_STT_COMPUTE_TYPE:-float16}"
else
  STT_COMPUTE_TYPE="${PUMPKIN_STT_COMPUTE_TYPE:-int8}"
fi

AUDIO_DEVICE="${PUMPKIN_AUDIO_DEVICE:-0}"
STT_DURATION="${PUMPKIN_STT_DURATION:-3.0}"
STT_MODEL="${PUMPKIN_STT_MODEL:-small}"
ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-0}"

mkdir -p "${LOG_DIR}"
rm -f "${LOG_DIR}"/*.log "${NLU_READY_FILE}" "${STT_READY_FILE}"

declare -A PIDS
declare -A LOGS

print_log_tail() {
  local name="$1"
  local log_file="${LOGS[$name]:-${LOG_DIR}/${name}.log}"
  echo
  echo "========== ${name} 마지막 로그 =========="
  [[ -f "${log_file}" ]] && tail -n 100 "${log_file}" || echo "로그 파일이 없습니다: ${log_file}"
  echo "========================================="
}

start_process() {
  local name="$1"
  shift
  local log_file="${LOG_DIR}/${name}.log"
  echo "[START] ${name}"
  stdbuf -oL -eL "$@" > >(tee -a "${log_file}") 2>&1 &
  PIDS["${name}"]=$!
  LOGS["${name}"]="${log_file}"
}

assert_alive() {
  local name="$1"
  local pid="${PIDS[$name]}"
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
  while (( elapsed < timeout_seconds )); do
    if [[ -f "${ready_file}" ]]; then
      echo "[READY] ${name}"
      cat "${ready_file}"
      return 0
    fi
    assert_alive "${name}" || return 1
    sleep 1
    ((elapsed += 1))
  done
  echo "[FAIL] ${name} 준비 시간이 초과되었습니다." >&2
  print_log_tail "${name}"
  return 1
}

cleanup() {
  echo
  echo "Stopping pumpkin ROS nodes..."
  for name in "${!PIDS[@]}"; do
    kill "${PIDS[$name]}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  rm -f "${NLU_READY_FILE}" "${STT_READY_FILE}"
}
trap cleanup EXIT INT TERM

"${CORE_PYTHON_BIN}" - <<PY
import ctranslate2
import faster_whisper
import rclpy
import robot_controller
print("Core/STT environment OK")
print("CTranslate2 CUDA devices:", ctranslate2.get_cuda_device_count())
PY

env -u LD_LIBRARY_PATH PYTHONNOUSERSITE=1 "${NLU_PYTHON_BIN}" - <<PY
import torch
print("NLU environment OK")
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
PY

echo
echo "Starting pumpkin ROS voice pipeline for PC..."
echo "nlu_device=${NLU_DEVICE}, stt_device=${STT_DEVICE}, stt_compute_type=${STT_COMPUTE_TYPE}"
echo "audio_device=${AUDIO_DEVICE}, stt_model=${STT_MODEL}, vision=${ENABLE_VISION}"
echo "logs=${LOG_DIR}"

start_process decision_node "${CORE_PYTHON_BIN}" -m robot_controller.decision_node_order_handoff
start_process response_manager_node "${CORE_PYTHON_BIN}" -m robot_controller.response_manager_node
start_process action_node "${CORE_PYTHON_BIN}" -m robot_controller.action_node_order_handoff
start_process tts_node "${CORE_PYTHON_BIN}" -m robot_controller.tts_node

if [[ "${ENABLE_VISION}" == "1" ]]; then
  start_process vision_node "${CORE_PYTHON_BIN}" -m robot_controller.vision_node
else
  echo "vision_node disabled (set PUMPKIN_ENABLE_VISION=1 to enable)"
fi

sleep 2
for node in decision_node response_manager_node action_node tts_node; do
  assert_alive "${node}"
done

start_process nlu_node bash "${NLU_RUNNER}"
wait_for_ready_file nlu_node "${NLU_READY_FILE}" "${STARTUP_TIMEOUT}"

start_process stt_node \
  "${CORE_PYTHON_BIN}" -m robot_controller.stt_node --ros-args \
  -p audio_device:="${AUDIO_DEVICE}" \
  -p duration:="${STT_DURATION}" \
  -p model_size:="${STT_MODEL}" \
  -p model_device:="${STT_DEVICE}" \
  -p compute_type:="${STT_COMPUTE_TYPE}"
wait_for_ready_file stt_node "${STT_READY_FILE}" "${STARTUP_TIMEOUT}"

echo
echo "Pumpkin ROS voice pipeline is READY on PC."
echo "NLU=${NLU_DEVICE}, STT=${STT_DEVICE}/${STT_COMPUTE_TYPE}"
echo "다른 터미널에서: python3 scripts/terminal_chat.py"
echo "Press Ctrl+C to stop all nodes."
echo

set +e
wait -n
status=$?
set -e

echo "[FAIL] ROS 노드 중 하나가 종료되었습니다. exit=${status}" >&2
for name in "${!PIDS[@]}"; do
  if ! kill -0 "${PIDS[$name]}" 2>/dev/null; then
    echo "종료된 프로세스: ${name}" >&2
    print_log_tail "${name}"
  fi
done
exit "${status}"
