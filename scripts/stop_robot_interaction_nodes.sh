#!/usr/bin/env bash
set -eo pipefail

# Stop only Pumpkin runtime processes from previous physical-demo launches.
# A stale duplicate Action/TTS/Decision node can subscribe to the same ROS topics
# and cause duplicate prompts or out-of-order speech in a new run.
PATTERNS=(
  "robot_controller.decision_node_order_handoff"
  "robot_controller.decision_node_additional_order"
  "robot_controller.response_manager_node"
  "robot_controller.face_personalization_node"
  "robot_controller.order_submission_node"
  "robot_controller.action_node_order_handoff"
  "robot_controller.face_display_node"
  "robot_controller.tts_node"
  "robot_controller.vision_node"
  "robot_controller.nlu_node"
  "robot_controller.stt_node"
  "robot_controller.motor_controller_node"
  "scripts/run_ros_voice_nodes.sh"
  "scripts/run_robot_interaction_demo.sh"
  "scripts/run_robot_with_monitor.sh"
  "apps/monitor-web/server.py"
  "pumpkin-monitor-profile"
)

found=0
for pattern in "${PATTERNS[@]}"; do
  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    found=1
    pkill -TERM -f "${pattern}" 2>/dev/null || true
  fi
done

if [[ "${found}" == "1" ]]; then
  echo "[CLEAN] 이전 Pumpkin ROS 실행 프로세스를 종료했습니다."
  sleep 1

  # Escalate only the exact Pumpkin process patterns that ignored SIGTERM.
  for pattern in "${PATTERNS[@]}"; do
    pkill -KILL -f "${pattern}" 2>/dev/null || true
  done
else
  echo "[CLEAN] 이전 Pumpkin ROS 프로세스 없음"
fi

rm -f /tmp/pumpkin_nlu_ready /tmp/pumpkin_stt_ready
