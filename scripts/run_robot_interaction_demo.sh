#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
CORE_PYTHON_BIN="${PUMPKIN_CORE_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
MOTOR_BACKEND="${PUMPKIN_MOTOR_BACKEND:-pca9685}"
MOTOR_LOG="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}/motor_controller_node.log"
ORDER_SUBMISSION_LOG="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}/order_submission_node.log"
ROS_PID=""
MOTOR_PID=""
ORDER_SUBMISSION_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  echo
  echo "Pumpkin physical interaction demo를 종료합니다..."
  if [[ -n "${ROS_PID}" ]]; then
    kill "${ROS_PID}" 2>/dev/null || true
  fi
  if [[ -n "${MOTOR_PID}" ]]; then
    kill "${MOTOR_PID}" 2>/dev/null || true
  fi
  if [[ -n "${ORDER_SUBMISSION_PID}" ]]; then
    kill "${ORDER_SUBMISSION_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [[ ! -x "${CORE_PYTHON_BIN}" ]]; then
  echo "코어 가상환경 Python을 찾을 수 없습니다: ${CORE_PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${ROOT_DIR}/scripts/run_ros_voice_nodes.sh" ]]; then
  echo "ROS 실행 스크립트를 찾을 수 없습니다." >&2
  exit 1
fi

# Reuse the already configured local POS Relay settings on the same Jetson.
# The file is gitignored and secrets are never printed. Explicit environment
# variables still win because shell variables are only filled when absent below.
POS_ENV_FILE="${ROOT_DIR}/apps/pos-web/.env"
if [[ -f "${POS_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${POS_ENV_FILE}"
  set +a
  echo "[ENV] local POS Relay settings loaded from apps/pos-web/.env"
fi
if [[ -z "${PUMPKIN_PREORDER_API_URL:-}" && -n "${POS_RELAY_BASE_URL:-}" ]]; then
  export PUMPKIN_PREORDER_API_URL="${POS_RELAY_BASE_URL}"
fi

# ROS setup scripts are not nounset-safe; keep -u disabled in this launcher.
source /opt/ros/humble/setup.bash

if [[ "${PUMPKIN_SKIP_BUILD:-0}" != "1" ]]; then
  echo "[BUILD] robot_controller 패키지를 빌드합니다."
  cd "${WORKSPACE}"
  colcon build --packages-select robot_controller --symlink-install
fi

source "${WORKSPACE}/install/setup.bash"
cd "${ROOT_DIR}"

export PYTHONNOUSERSITE=1
export PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/ros2_ws/src/robot_controller:${PYTHONPATH:-}"
export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export PUMPKIN_ENABLE_TEGRASTATS="${PUMPKIN_ENABLE_TEGRASTATS:-0}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-cuda}"
export PUMPKIN_ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-1}"
export PUMPKIN_ENABLE_FACE_DISPLAY="${PUMPKIN_ENABLE_FACE_DISPLAY:-1}"
export PUMPKIN_ENABLE_ARM="${PUMPKIN_ENABLE_ARM:-false}"
export PUMPKIN_ESP32_PORT="${PUMPKIN_ESP32_PORT:-auto}"

case "${PUMPKIN_ENABLE_ARM,,}" in
  1|true|yes|on) ARM_ENABLED=true ;;
  *) ARM_ENABLED=false ;;
esac

# Physical gesture tuning: allow natural NOD/SHAKE shortly after robot speech,
# while the separate candidate hold still gives speech_detected priority.
export PUMPKIN_GESTURE_RESPONSE_GRACE_SEC="${PUMPKIN_GESTURE_RESPONSE_GRACE_SEC:-0.20}"

# Physical ReSpeaker VAD profile.
# The earlier 3500 RMS x 7 blocks profile missed ordinary quiet/short Korean
# utterances on the real robot. Start detection is now more sensitive while the
# existing endpoint detector remains unchanged.
export PUMPKIN_STT_SPEECH_THRESHOLD="${PUMPKIN_STT_SPEECH_THRESHOLD:-2800.0}"
export PUMPKIN_STT_SPEECH_START_BLOCKS="${PUMPKIN_STT_SPEECH_START_BLOCKS:-4}"
export PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS="${PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS:-2}"

# Ambient medians were roughly RMS 800-1350. Use a higher end floor than the old
# 850 value, but keep it well below the speech-start threshold. The adaptive end
# detector may raise this floor from the measured pre-roll noise, capped at 75%
# of the start threshold so softer syllables are not treated as silence too early.
export PUMPKIN_STT_END_THRESHOLD="${PUMPKIN_STT_END_THRESHOLD:-1800.0}"
export PUMPKIN_STT_END_CEILING_RATIO="${PUMPKIN_STT_END_CEILING_RATIO:-0.75}"
export PUMPKIN_STT_SILENCE_DURATION="${PUMPKIN_STT_SILENCE_DURATION:-0.6}"

# max_duration is only a safety cap when endpoint detection fails. Keep enough
# room for long natural orders instead of using it as the normal stop condition.
export PUMPKIN_STT_MAX_DURATION="${PUMPKIN_STT_MAX_DURATION:-10.0}"

# TTS reports done only after aplay exits. Keep just 50 ms for the physical
# speaker's acoustic tail so customers can answer essentially as soon as the
# robot finishes speaking without waiting for the monitor prompt.
export PUMPKIN_STT_POST_TTS_GUARD="${PUMPKIN_STT_POST_TTS_GUARD:-0.05}"

mkdir -p "$(dirname "${MOTOR_LOG}")"

if [[ "${PUMPKIN_ENABLE_VISION}" != "1" ]]; then
  echo "[WARN] PUMPKIN_ENABLE_VISION=${PUMPKIN_ENABLE_VISION}: 실제 사람 감지/NOD/SHAKE가 비활성화됩니다."
fi
if [[ "${PUMPKIN_ENABLE_FACE_DISPLAY}" != "1" ]]; then
  echo "[WARN] PUMPKIN_ENABLE_FACE_DISPLAY=${PUMPKIN_ENABLE_FACE_DISPLAY}: 얼굴 LCD가 비활성화됩니다."
fi
if [[ "${MOTOR_BACKEND}" != "pca9685" ]]; then
  echo "[WARN] motor backend=${MOTOR_BACKEND}: 실제 PCA9685 서보가 아닌 모드입니다."
fi
if [[ "${ARM_ENABLED}" == "true" ]]; then
  echo "[SAFETY] 팔 동작 활성화: 실행 전에 팔이 차렷(HOME) 자세인지 확인하세요."
else
  echo "[INFO] 팔 동작 비활성화. 차렷 자세 확인 후 PUMPKIN_ENABLE_ARM=true로 켤 수 있습니다."
fi
if [[ -z "${PUMPKIN_PREORDER_API_URL:-}" && -z "${PUMPKIN_ORDER_API_URL:-}" ]]; then
  echo "[WARN] Cloud Relay URL이 없습니다. ROBOT 주문은 POS에 전송되지 않습니다." >&2
fi

# Fail early when the physical-demo-only software dependencies are missing.
# PCA9685 hardware itself is optional at runtime: if it is powered/connected,
# the real motor controller is used; otherwise the dialogue pipeline continues
# without head motion.
"${CORE_PYTHON_BIN}" - <<'PY'
missing = []
for module in ("cv2", "mediapipe", "serial", "edge_tts", "Jetson.GPIO"):
    try:
        __import__(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

try:
    import adafruit_servokit  # noqa: F401
except Exception as exc:
    missing.append(f"adafruit_servokit: {exc}")

try:
    from robot_controller.head_motion_node import normalize_head_command
    from robot_controller.arm_motion import normalize_arm_action
    assert normalize_head_command("NOD") == "NOD"
    assert normalize_arm_action("POINT_RIGHT") == "POINT_RIGHT"
except Exception as exc:
    missing.append(f"robot_controller.head_motion_node: {exc}")

if missing:
    raise SystemExit(
        "Physical demo dependency check failed:\n- " + "\n- ".join(missing)
    )

print("[CHECK] vision / face / TTS / Jetson.GPIO / PCA9685 Python dependencies OK")
PY

echo
echo "============================================================"
echo " Pumpkin Physical Interaction Demo"
echo "============================================================"
echo "입력 : Camera presence + customer NOD/SHAKE + microphone VAD"
echo "판단 : STT -> NLU -> Decision -> Response Manager -> Action"
echo "출력 : Speaker TTS + ESP32 face LCD + PCA9685 head/arm servos"
echo "주문 : final dialogue -> ROBOT -> Cloud Relay -> POS"
echo "motor backend=${MOTOR_BACKEND}, arm_enabled=${ARM_ENABLED}"
echo "vision=${PUMPKIN_ENABLE_VISION}, face=${PUMPKIN_ENABLE_FACE_DISPLAY}"
echo "stt start=${PUMPKIN_STT_SPEECH_THRESHOLD} x ${PUMPKIN_STT_SPEECH_START_BLOCKS} blocks, end=${PUMPKIN_STT_END_THRESHOLD}, silence=${PUMPKIN_STT_SILENCE_DURATION}s, max=${PUMPKIN_STT_MAX_DURATION}s, post_tts_guard=${PUMPKIN_STT_POST_TTS_GUARD}s"
echo "============================================================"
echo

# Submit only the final completed customer order. ORDER_CONFIRMED candidates are
# cached inside this node; the actual POST happens after ORDER_FINISHED.
echo "[START] order_submission_node"
stdbuf -oL -eL "${CORE_PYTHON_BIN}" \
  -m robot_controller.order_submission_node \
  > >(tee -a "${ORDER_SUBMISSION_LOG}") 2>&1 &
ORDER_SUBMISSION_PID=$!

sleep 1
if ! kill -0 "${ORDER_SUBMISSION_PID}" 2>/dev/null; then
  echo "[WARN] order_submission_node를 시작하지 못했습니다. 로봇 주문 POS 연동 없이 계속합니다." >&2
  tail -n 30 "${ORDER_SUBMISSION_LOG}" 2>/dev/null || true
  wait "${ORDER_SUBMISSION_PID}" 2>/dev/null || true
  ORDER_SUBMISSION_PID=""
else
  echo "[OK] ROBOT 주문 Cloud Relay 전송 노드 준비됨."
fi

# MotorController is deliberately kept as a separate hardware executor.
# ActionNode publishes semantic /robot_action.head, HeadMotionNode converts it
# to /motor_command, and this process alone owns the PCA9685 hardware.
# Hardware availability is optional so a powered-off/disconnected PCA9685 does
# not block STT/NLU/TTS/vision/face testing.
echo "[START] motor_controller_node (${MOTOR_BACKEND})"
stdbuf -oL -eL "${CORE_PYTHON_BIN}" \
  -m robot_controller.motor_controller_node \
  --ros-args -p backend:="${MOTOR_BACKEND}" -p arm_enabled:="${ARM_ENABLED}" \
  > >(tee -a "${MOTOR_LOG}") 2>&1 &
MOTOR_PID=$!

sleep 1
if ! kill -0 "${MOTOR_PID}" 2>/dev/null; then
  echo "[WARN] PCA9685/모터 컨트롤러를 사용할 수 없습니다. 모터 없이 계속 실행합니다." >&2
  tail -n 20 "${MOTOR_LOG}" 2>/dev/null || true
  wait "${MOTOR_PID}" 2>/dev/null || true
  MOTOR_PID=""
else
  echo "[OK] 모터 컨트롤러 연결됨 - 실제 목/팔 설정을 사용합니다."
fi

# The existing launcher owns STT/NLU/Decision/Response/Action/TTS/Face/Vision.
echo "[START] complete ROS dialogue pipeline"
bash "${ROOT_DIR}/scripts/run_ros_voice_nodes.sh" &
ROS_PID=$!

echo
echo "실제 테스트 순서:"
echo "  1) 카메라 앞에 서서 고객 감지를 기다립니다."
echo "  2) 로봇 인사/TTS가 끝난 즉시 주문을 말합니다."
echo "  3) 주문 확인에서는 '네/아니요' 또는 NOD/SHAKE 중 하나로 답합니다."
echo "  4) 주문을 최종 종료하면 source=ROBOT 주문이 Cloud Relay/POS에 생성되는지 확인합니다."
echo "  5) LCD 표정과 목/팔 동작이 /robot_action에 맞게 실행되는지 확인합니다."
echo "Ctrl+C로 종료합니다."
echo

# The ROS dialogue pipeline is the required runtime. The motor controller and
# Cloud order submission helper are isolated so hardware/network failures do not
# kill the remaining dialogue pipeline.
set +e
wait "${ROS_PID}"
status=$?
set -e

if ! kill -0 "${ROS_PID}" 2>/dev/null; then
  echo "[INFO] run_ros_voice_nodes.sh 종료됨. exit=${status}" >&2
fi
if [[ -n "${MOTOR_PID}" ]] && ! kill -0 "${MOTOR_PID}" 2>/dev/null; then
  echo "[WARN] motor_controller_node가 종료되었지만 대화 파이프라인은 유지되었습니다." >&2
  tail -n 20 "${MOTOR_LOG}" 2>/dev/null || true
fi
if [[ -n "${ORDER_SUBMISSION_PID}" ]] && ! kill -0 "${ORDER_SUBMISSION_PID}" 2>/dev/null; then
  echo "[WARN] order_submission_node가 종료되어 이후 ROBOT 주문은 POS로 전송되지 않습니다." >&2
  tail -n 30 "${ORDER_SUBMISSION_LOG}" 2>/dev/null || true
fi

exit "${status}"
