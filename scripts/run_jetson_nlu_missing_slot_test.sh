#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_ROOT="${PUMPKIN_RUNTIME_ROOT:-${HOME}/pumpkin}"
PYTHON_BIN="${RUNTIME_ROOT}/.venv/bin/python"
MODEL_DIR="${RUNTIME_ROOT}/nlu/saved_models/structure_b_item_query_decoder"
TEST_ROS_DOMAIN_ID="${PUMPKIN_TEST_ROS_DOMAIN_ID:-79}"
LOG_DIR="${PUMPKIN_NLU_TEST_LOG_DIR:-/tmp/pumpkin-nlu-slot-test}"
NLU_READY_FILE="${LOG_DIR}/nlu_ready"
STARTUP_TIMEOUT="${PUMPKIN_NLU_TEST_TIMEOUT:-240}"

DECISION_PID=""
ACTION_PID=""
NLU_PID=""

cleanup() {
  for pid in "${NLU_PID}" "${ACTION_PID}" "${DECISION_PID}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
  rm -f "${NLU_READY_FILE}"
}
trap cleanup EXIT INT TERM

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[ERROR] 기존 Pumpkin 가상환경을 찾을 수 없습니다: ${PYTHON_BIN}" >&2
  exit 1
fi

for required in "${MODEL_DIR}/best_model.pt" "${MODEL_DIR}/tokenizer"; do
  if [[ ! -e "${required}" ]]; then
    echo "[ERROR] NLU 모델 파일을 찾을 수 없습니다: ${required}" >&2
    exit 1
  fi
done

set +u
source /opt/ros/humble/setup.bash
set -u

export ROS_DOMAIN_ID="${TEST_ROS_DOMAIN_ID}"
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PUMPKIN_PROJECT_ROOT="${RUNTIME_ROOT}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-cpu}"
export PUMPKIN_NLU_READY_FILE="${NLU_READY_FILE}"
export PYTHONPATH="${PROJECT_ROOT}/ros2_ws/src/robot_controller:${RUNTIME_ROOT}:${PYTHONPATH:-}"

mkdir -p "${LOG_DIR}"
rm -f "${LOG_DIR}"/*.log "${NLU_READY_FILE}"

echo "[INFO] Branch source: ${PROJECT_ROOT}"
echo "[INFO] Runtime/model root: ${RUNTIME_ROOT}"
echo "[INFO] Isolated ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo "[INFO] NLU device=${PUMPKIN_NLU_DEVICE}"
echo "[INFO] Logs=${LOG_DIR}"

"${PYTHON_BIN}" - <<'PY'
import robot_controller
from robot_controller import decision_node, nlu_node

print(f"robot_controller={robot_controller.__file__}")
print(f"decision_node={decision_node.__file__}")
print(f"nlu_node={nlu_node.__file__}")
PY

EXISTING_NODES="$(ros2 node list 2>/dev/null || true)"
if grep -Eq '(^|/)(decision_node|action_node|nlu_node)$' <<<"${EXISTING_NODES}"; then
  echo "[ERROR] 테스트 도메인 ${ROS_DOMAIN_ID}에 동일 노드가 이미 실행 중입니다." >&2
  echo "다른 도메인 예: PUMPKIN_TEST_ROS_DOMAIN_ID=80 bash scripts/run_jetson_nlu_missing_slot_test.sh" >&2
  exit 2
fi

"${PYTHON_BIN}" -m robot_controller.decision_node \
  >"${LOG_DIR}/decision_node.log" 2>&1 &
DECISION_PID=$!

"${PYTHON_BIN}" -m robot_controller.action_node \
  >"${LOG_DIR}/action_node.log" 2>&1 &
ACTION_PID=$!

"${PYTHON_BIN}" -m robot_controller.nlu_node \
  >"${LOG_DIR}/nlu_node.log" 2>&1 &
NLU_PID=$!

echo "[WAIT] 실제 NLU 모델 로딩 중... 최대 ${STARTUP_TIMEOUT}초"
for _ in $(seq 1 "${STARTUP_TIMEOUT}"); do
  if [[ -f "${NLU_READY_FILE}" ]]; then
    break
  fi

  for name_pid in \
    "decision_node:${DECISION_PID}" \
    "action_node:${ACTION_PID}" \
    "nlu_node:${NLU_PID}"; do
    name="${name_pid%%:*}"
    pid="${name_pid##*:}"
    if ! kill -0 "${pid}" 2>/dev/null; then
      echo "[ERROR] ${name}가 준비 중 종료되었습니다." >&2
      echo "--- ${name} log ---" >&2
      cat "${LOG_DIR}/${name}.log" >&2 || true
      exit 3
    fi
  done
  sleep 1
done

if [[ ! -f "${NLU_READY_FILE}" ]]; then
  echo "[ERROR] NLU 모델 준비 시간이 초과되었습니다." >&2
  echo "--- nlu_node log ---" >&2
  cat "${LOG_DIR}/nlu_node.log" >&2 || true
  exit 4
fi

echo "[READY] NLU"
cat "${NLU_READY_FILE}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/jetson_test_nlu_missing_slot_dialog.py"

echo
echo "NLU log:      ${LOG_DIR}/nlu_node.log"
echo "Decision log: ${LOG_DIR}/decision_node.log"
echo "Action log:   ${LOG_DIR}/action_node.log"
