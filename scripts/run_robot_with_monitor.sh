#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Physical robot default profile. These defaults match the currently calibrated
# Jetson + ReSpeaker Lite + PCA9685 setup, while still allowing any value to be
# overridden by prefixing an environment variable on the launch command.
export PUMPKIN_MOTOR_BACKEND="${PUMPKIN_MOTOR_BACKEND:-pca9685}"
export PUMPKIN_ENABLE_ARM="${PUMPKIN_ENABLE_ARM:-true}"
export PUMPKIN_VISION_STARTUP_TIMEOUT="${PUMPKIN_VISION_STARTUP_TIMEOUT:-30}"
export PUMPKIN_STT_SPEECH_THRESHOLD="${PUMPKIN_STT_SPEECH_THRESHOLD:-150}"
export PUMPKIN_STT_SPEECH_START_BLOCKS="${PUMPKIN_STT_SPEECH_START_BLOCKS:-4}"
export PUMPKIN_STT_END_THRESHOLD="${PUMPKIN_STT_END_THRESHOLD:-80}"
export PUMPKIN_STT_END_CEILING_RATIO="${PUMPKIN_STT_END_CEILING_RATIO:-0.75}"
export PUMPKIN_STT_SILENCE_DURATION="${PUMPKIN_STT_SILENCE_DURATION:-0.6}"
export PUMPKIN_TTS_VOLUME="${PUMPKIN_TTS_VOLUME:-+0%}"

MONITOR_DIR="${ROOT_DIR}/apps/monitor-web"
MONITOR_PORT="${PUMPKIN_MONITOR_WEB_PORT:-8770}"
MONITOR_URL="http://127.0.0.1:${MONITOR_PORT}"
MONITOR_LOG="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}/monitor_web.log"
CHROMIUM_LOG="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}/monitor_chromium.log"
DISPLAY_ID="${PUMPKIN_MONITOR_DISPLAY:-:0}"
DISPLAY_OUTPUT="${PUMPKIN_MONITOR_OUTPUT:-DP-1}"
DISPLAY_ROTATION="${PUMPKIN_MONITOR_ROTATION:-inverted}"
USER_ID="$(id -u)"
PROJECT_USER_DIR="$(dirname "${ROOT_DIR}")"
XAUTHORITY_PATH="${PUMPKIN_MONITOR_XAUTHORITY:-}"
if [[ -z "${XAUTHORITY_PATH}" ]]; then
  for candidate in "${PROJECT_USER_DIR}/.Xauthority" "/run/user/${USER_ID}/gdm/Xauthority"; do
    if [[ -r "${candidate}" ]]; then
      XAUTHORITY_PATH="${candidate}"
      break
    fi
  done
fi
PROFILE_DIR="${PROJECT_USER_DIR}/snap/chromium/common/pumpkin-monitor-profile"
ARM_ENABLED="${PUMPKIN_ENABLE_ARM:-true}"
MONITOR_PID=""
ROBOT_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  echo
  echo "[STOP] Pumpkin robot + monitor launcher를 종료합니다."

  if [[ -n "${ROBOT_PID}" ]] && kill -0 "${ROBOT_PID}" 2>/dev/null; then
    kill -INT "${ROBOT_PID}" 2>/dev/null || true
  fi

  if [[ -n "${MONITOR_PID}" ]] && kill -0 "${MONITOR_PID}" 2>/dev/null; then
    kill "${MONITOR_PID}" 2>/dev/null || true
  fi

  pkill -f 'pumpkin-monitor-profile' 2>/dev/null || true
  wait 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT INT TERM

if [[ ! -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  echo "[FAIL] .venv가 없습니다: ${ROOT_DIR}/.venv" >&2
  exit 1
fi
if [[ ! -f "${MONITOR_DIR}/server.py" ]]; then
  echo "[FAIL] monitor-web server.py를 찾을 수 없습니다." >&2
  exit 1
fi
if [[ ! -f "${ROOT_DIR}/scripts/run_robot_interaction_demo.sh" ]]; then
  echo "[FAIL] run_robot_interaction_demo.sh를 찾을 수 없습니다." >&2
  exit 1
fi
if ! command -v snap >/dev/null 2>&1; then
  echo "[FAIL] snap 명령을 찾을 수 없습니다." >&2
  exit 1
fi
if ! snap list chromium >/dev/null 2>&1; then
  echo "[FAIL] Snap Chromium이 설치되어 있지 않습니다." >&2
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

mkdir -p "$(dirname "${MONITOR_LOG}")" "${PROFILE_DIR}"

export PUMPKIN_MONITOR_WEB_PORT="${MONITOR_PORT}"
export PUMPKIN_ENABLE_ARM="${ARM_ENABLED}"

echo "============================================================"
echo " Pumpkin Robot + 5-inch Monitor - ONE COMMAND"
echo "============================================================"
echo "monitor  : ${MONITOR_URL}"
echo "display  : ${DISPLAY_ID} (800x480 kiosk)"
echo "output   : ${DISPLAY_OUTPUT}"
echo "rotation : ${DISPLAY_ROTATION}"
echo "arm      : ${ARM_ENABLED}"
echo "============================================================"
echo

# Prevent the GNOME/X11 display from blanking during the kiosk demo. Failure is
# non-fatal because the GUI session may use a different power-management path.
if [[ -n "${XAUTHORITY_PATH}" ]]; then
  echo "[INFO] Xauthority: ${XAUTHORITY_PATH}"
else
  echo "[INFO] readable Xauthority 파일 없이 현재 사용자 X 세션을 사용합니다."
fi

DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" xset dpms force on 2>/dev/null || true
DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" xset s reset 2>/dev/null || true
DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" xset s off 2>/dev/null || true
DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" xset s noblank 2>/dev/null || true
DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" xset -dpms 2>/dev/null || true

# The physical 5-inch LCD is mounted upside down so its HDMI/power cables can
# exit toward the bottom of the robot body. Rotate the X11 output before the
# kiosk opens so every rendered screen, not only the web page, is upright.
if command -v xrandr >/dev/null 2>&1; then
  if DISPLAY="${DISPLAY_ID}" XAUTHORITY="${XAUTHORITY_PATH}" \
    xrandr --output "${DISPLAY_OUTPUT}" --rotate "${DISPLAY_ROTATION}"; then
    echo "[OK] monitor rotation applied: ${DISPLAY_OUTPUT} -> ${DISPLAY_ROTATION}"
  else
    echo "[WARN] monitor rotation failed: output=${DISPLAY_OUTPUT}, rotation=${DISPLAY_ROTATION}" >&2
  fi
else
  echo "[WARN] xrandr 명령을 찾지 못해 화면 회전을 건너뜁니다." >&2
fi
# Stop only the dedicated customer-monitor Chromium profile from an older run.
pkill -f 'pumpkin-monitor-profile' 2>/dev/null || true

# Start the customer monitor backend first so Chromium never lands on an
# ERR_CONNECTION_REFUSED page during normal startup.
echo "[START] 5-inch monitor web server"
(
  cd "${MONITOR_DIR}"
  exec python3 server.py
) >"${MONITOR_LOG}" 2>&1 &
MONITOR_PID=$!

# Wait until the HTTP endpoint is actually reachable before opening kiosk mode.
MONITOR_READY=0
for _ in $(seq 1 50); do
  if ! kill -0 "${MONITOR_PID}" 2>/dev/null; then
    echo "[FAIL] monitor-web server가 시작 중 종료되었습니다." >&2
    tail -n 80 "${MONITOR_LOG}" >&2 || true
    exit 1
  fi
  if curl -fsS "${MONITOR_URL}/" >/dev/null 2>&1; then
    MONITOR_READY=1
    break
  fi
  sleep 0.2
done

if [[ "${MONITOR_READY}" != "1" ]]; then
  echo "[FAIL] ${MONITOR_URL} 응답을 기다리다 시간 초과되었습니다." >&2
  tail -n 80 "${MONITOR_LOG}" >&2 || true
  exit 1
fi

echo "[OK] monitor-web ready"

# Launch Chromium on the Jetson's physical X11 session. GPU rendering is
# disabled because the Jetson Snap Chromium EGL path was unstable on this unit;
# this customer UI only needs normal HTML/CSS rendering.
echo "[START] 5-inch Chromium kiosk"
DISPLAY="${DISPLAY_ID}" \
XAUTHORITY="${XAUTHORITY_PATH}" \
XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${USER_ID}/bus" \
nohup snap run chromium \
  --ozone-platform=x11 \
  --disable-gpu \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  --window-position=0,0 \
  --window-size=800,480 \
  --disable-session-crashed-bubble \
  --force-device-scale-factor=1 \
  --kiosk \
  --app="${MONITOR_URL}/?kiosk=1" \
  >"${CHROMIUM_LOG}" 2>&1 &

sleep 2
if ! pgrep -f 'pumpkin-monitor-profile' >/dev/null 2>&1; then
  echo "[FAIL] Chromium kiosk가 실행되지 않았습니다." >&2
  tail -n 80 "${CHROMIUM_LOG}" >&2 || true
  exit 1
fi

echo "[OK] 5-inch kiosk ready"
echo

echo "[START] 팔·목·카메라·음성·얼굴 LCD 통합 로봇 파이프라인"
bash "${ROOT_DIR}/scripts/run_robot_interaction_demo.sh" &
ROBOT_PID=$!

set +e
wait "${ROBOT_PID}"
ROBOT_STATUS=$?
set -e

if [[ "${ROBOT_STATUS}" -ne 0 ]]; then
  echo "[FAIL] 로봇 주문 파이프라인이 종료되었습니다. exit=${ROBOT_STATUS}" >&2
fi

exit "${ROBOT_STATUS}"
