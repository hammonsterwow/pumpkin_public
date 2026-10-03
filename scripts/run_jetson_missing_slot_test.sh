#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE="${PROJECT_ROOT}/ros2_ws"
DECISION_LOG="/tmp/pumpkin_decision_slot_test.log"
ACTION_LOG="/tmp/pumpkin_action_slot_test.log"
TEST_ROS_DOMAIN_ID="${PUMPKIN_TEST_ROS_DOMAIN_ID:-77}"
DECISION_PID=""
ACTION_PID=""

cleanup() {
  if [[ -n "${ACTION_PID}" ]] && kill -0 "${ACTION_PID}" 2>/dev/null; then
    kill "${ACTION_PID}" 2>/dev/null || true
    wait "${ACTION_PID}" 2>/dev/null || true
  fi
  if [[ -n "${DECISION_PID}" ]] && kill -0 "${DECISION_PID}" 2>/dev/null; then
    kill "${DECISION_PID}" 2>/dev/null || true
    wait "${DECISION_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ROS 2 setup scripts may read variables that are intentionally unset.
# Keep nounset disabled only while sourcing environment setup files.
set +u
source /opt/ros/humble/setup.bash

if [[ -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  source "${PROJECT_ROOT}/.venv/bin/activate"
fi
set -u

# Keep this test isolated from a currently running Pumpkin pipeline.
# Override with PUMPKIN_TEST_ROS_DOMAIN_ID when domain 77 is already in use.
export ROS_DOMAIN_ID="${TEST_ROS_DOMAIN_ID}"
echo "[INFO] Isolated ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"

cd "${WORKSPACE}"
colcon build --packages-select robot_controller --symlink-install

set +u
source "${WORKSPACE}/install/setup.bash"
set -u

EXISTING_NODES="$(ros2 node list 2>/dev/null || true)"
if grep -Eq '(^|/)decision_node$|(^|/)action_node$' <<<"${EXISTING_NODES}"; then
  echo "[ERROR] 테스트 도메인 ${ROS_DOMAIN_ID}에서 decision_node 또는 action_node가 이미 실행 중입니다."
  echo "다른 도메인으로 실행하세요: PUMPKIN_TEST_ROS_DOMAIN_ID=78 bash scripts/run_jetson_missing_slot_test.sh"
  exit 2
fi

: >"${DECISION_LOG}"
: >"${ACTION_LOG}"
ros2 run robot_controller decision_node >"${DECISION_LOG}" 2>&1 &
DECISION_PID=$!
ros2 run robot_controller action_node >"${ACTION_LOG}" 2>&1 &
ACTION_PID=$!

for _ in $(seq 1 40); do
  NODES="$(ros2 node list 2>/dev/null || true)"
  if grep -Eq '(^|/)decision_node$' <<<"${NODES}" \
    && grep -Eq '(^|/)action_node$' <<<"${NODES}"; then
    break
  fi
  sleep 0.25
done

NODES="$(ros2 node list 2>/dev/null || true)"
if ! grep -Eq '(^|/)decision_node$' <<<"${NODES}" \
  || ! grep -Eq '(^|/)action_node$' <<<"${NODES}"; then
  echo "[ERROR] ROS2 테스트 노드가 정상적으로 시작되지 않았습니다."
  echo "--- decision log ---"
  cat "${DECISION_LOG}"
  echo "--- action log ---"
  cat "${ACTION_LOG}"
  exit 3
fi

python3 "${SCRIPT_DIR}/jetson_test_missing_slot_dialog.py"

echo
echo "Decision log: ${DECISION_LOG}"
echo "Action log:   ${ACTION_LOG}"
