#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/nlu/saved_models/structure_b_item_query_decoder"
HOST="${PUMPKIN_API_HOST:-0.0.0.0}"
PORT="${PUMPKIN_API_PORT:-8000}"
ROS_SCRIPT="${ROOT_DIR}/scripts/run_ros_voice_nodes.sh"
API_SCRIPT="${ROOT_DIR}/scripts/run_web_api.sh"
STT_READY_FILE="/tmp/pumpkin_stt_ready"
STARTUP_TIMEOUT="${PUMPKIN_STARTUP_TIMEOUT:-240}"

cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  source "${ROOT_DIR}/.venv/bin/activate"
else
  echo "가상환경이 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi

export PYTHONNOUSERSITE=1

for required in \
  "${MODEL_DIR}/best_model.pt" \
  "${MODEL_DIR}/tokenizer"; do
  if [[ ! -e "${required}" ]]; then
    echo "필수 모델 파일이 없습니다: ${required}" >&2
    exit 1
  fi
done

if [[ ! -f "${ROOT_DIR}/ros2_ws/install/setup.bash" ]]; then
  echo "ROS2 워크스페이스가 빌드되지 않았습니다." >&2
  echo "cd ${ROOT_DIR}/ros2_ws && colcon build --packages-select robot_controller --symlink-install" >&2
  exit 1
fi

python - <<'PY'
import sys
import ctranslate2
import torch
import transformers

print("python:", sys.executable)
print("torch:", torch.__version__)
print("transformers:", transformers.__version__)
print("ctranslate2:", ctranslate2.__version__)
print("ctranslate2_path:", ctranslate2.__file__)
print("ctranslate2_cuda_devices:", ctranslate2.get_cuda_device_count())
PY

export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export PUMPKIN_NLU_MODEL_DIR="${MODEL_DIR}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-auto}"
export PUMPKIN_NLU_CONFIDENCE_THRESHOLD="${PUMPKIN_NLU_CONFIDENCE_THRESHOLD:-0.5}"
# The physical robot uses camera presence + customer NOD/SHAKE by default.
# Headless development can still disable it with PUMPKIN_ENABLE_VISION=0.
export PUMPKIN_ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-1}"

declare -A PIDS

cleanup() {
  echo
  echo "Pumpkin 전체 파이프라인을 종료합니다..."
  for name in "${!PIDS[@]}"; do
    kill "${PIDS[$name]}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

component_alive() {
  local name="$1"
  kill -0 "${PIDS[$name]}" 2>/dev/null
}

report_stopped_components() {
  for name in "${!PIDS[@]}"; do
    if ! component_alive "${name}"; then
      echo "종료된 구성요소: ${name}" >&2
    fi
  done
}

rm -f "${STT_READY_FILE}"

echo
echo "Pumpkin 전체 파이프라인을 시작합니다..."

bash "${ROS_SCRIPT}" &
PIDS[ros]="$!"

bash "${API_SCRIPT}" "${HOST}" "${PORT}" &
PIDS[api]="$!"

cd "${ROOT_DIR}/web"
if [[ ! -d node_modules ]]; then
  npm install
fi

npm run dev &
PIDS[web]="$!"

elapsed=0
while (( elapsed < STARTUP_TIMEOUT )); do
  if ! component_alive ros || ! component_alive api || ! component_alive web; then
    echo "[FAIL] 준비 과정에서 구성요소가 종료되었습니다." >&2
    report_stopped_components
    exit 1
  fi

  if [[ -f "${STT_READY_FILE}" ]] && curl -fsS "http://127.0.0.1:${PORT}/api/ros/status" >/dev/null 2>&1; then
    break
  fi

  sleep 1
  ((elapsed += 1))
done

if (( elapsed >= STARTUP_TIMEOUT )); then
  echo "[FAIL] 전체 파이프라인 준비 시간이 초과되었습니다." >&2
  echo "ROS 로그 위치: /tmp/pumpkin-logs" >&2
  exit 1
fi

printf '\nPumpkin 전체 파이프라인 READY\n'
printf 'STT: faster-whisper small / CUDA int8\n'
printf 'NLU: saved_models/structure_b_item_query_decoder / %s\n' "${PUMPKIN_NLU_DEVICE}"
printf 'Vision: %s\n' "${PUMPKIN_ENABLE_VISION}"
printf '웹 주소: http://JETSON_IP:3000\n'
printf 'API 주소: http://JETSON_IP:%s\n\n' "${PORT}"
printf 'Ctrl+C를 누르면 모든 프로세스가 함께 종료됩니다.\n\n'

set +e
wait -n
status=$?
set -e

echo "[FAIL] 실행 중 구성요소 하나가 종료되었습니다. exit=${status}" >&2
report_stopped_components
exit "${status}"
