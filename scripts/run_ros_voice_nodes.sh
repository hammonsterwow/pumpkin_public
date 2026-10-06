#!/usr/bin/env bash
set -eo pipefail
set +u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
CORE_PYTHON_BIN="${PUMPKIN_CORE_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
NLU_PYTHON_BIN="${PUMPKIN_NLU_PYTHON:-${ROOT_DIR}/.venv-nlu/bin/python}"
NLU_RUNNER="${ROOT_DIR}/scripts/run_nlu_node_cuda.sh"
CAMERA_RESOLVER="${ROOT_DIR}/scripts/resolve_camera_device.py"
LOG_DIR="${PUMPKIN_LOG_DIR:-/tmp/pumpkin-logs}"
NLU_READY_FILE="/tmp/pumpkin_nlu_ready"
STT_READY_FILE="/tmp/pumpkin_stt_ready"
STARTUP_TIMEOUT="${PUMPKIN_STARTUP_TIMEOUT:-180}"
VISION_STARTUP_TIMEOUT="${PUMPKIN_VISION_STARTUP_TIMEOUT:-12}"
ENABLE_TEGRASTATS="${PUMPKIN_ENABLE_TEGRASTATS:-1}"
TEGRASTATS_INTERVAL_MS="${PUMPKIN_TEGRASTATS_INTERVAL_MS:-1000}"

unset LD_LIBRARY_PATH
source /opt/ros/humble/setup.bash
source "${WORKSPACE}/install/setup.bash"

if [[ ! -x "${CORE_PYTHON_BIN}" ]]; then
  echo "코어/STT 가상환경 Python을 찾을 수 없습니다: ${CORE_PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -x "${NLU_PYTHON_BIN}" ]]; then
  echo "NLU 가상환경 Python을 찾을 수 없습니다: ${NLU_PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${NLU_RUNNER}" ]]; then
  echo "NLU 실행 스크립트를 찾을 수 없습니다: ${NLU_RUNNER}" >&2
  exit 1
fi

export PYTHONNOUSERSITE=1
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -S "${XDG_RUNTIME_DIR}/pulse/native" ]]; then
  export PULSE_SERVER="${PULSE_SERVER:-unix:${XDG_RUNTIME_DIR}/pulse/native}"
fi

export LD_LIBRARY_PATH="${ROOT_DIR}/.venv/lib:/usr/local/cuda/lib64:/usr/local/cuda/targets/aarch64-linux/lib:${LD_LIBRARY_PATH:-}"
export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export PUMPKIN_NLU_DEVICE="${PUMPKIN_NLU_DEVICE:-cuda}"

resolve_audio_device() {
  if [[ -n "${PUMPKIN_AUDIO_DEVICE:-}" ]]; then
    printf '%s\n' "${PUMPKIN_AUDIO_DEVICE}"
    return
  fi

  "${CORE_PYTHON_BIN}" - <<'PY'
import sounddevice as sd

preferred_names = ("respeaker lite", "respeaker")
devices = sd.query_devices()

for preferred_name in preferred_names:
    for index, device in enumerate(devices):
        name = str(device.get("name", "")).lower()
        input_channels = int(device.get("max_input_channels", 0))
        if preferred_name in name and input_channels > 0:
            print(index)
            raise SystemExit(0)

default_input = sd.default.device[0]
print(int(default_input) if default_input is not None else -1)
PY
}

resolve_audio_sample_rate() {
  if [[ -n "${PUMPKIN_AUDIO_SAMPLE_RATE:-}" ]]; then
    printf '%s\n' "${PUMPKIN_AUDIO_SAMPLE_RATE}"
    return
  fi

  "${CORE_PYTHON_BIN}" - "${AUDIO_DEVICE}" <<'PY'
import sys
import sounddevice as sd

device_index = int(sys.argv[1])
device = None if device_index < 0 else device_index

try:
    info = sd.query_devices(device, "input")
    print(int(round(float(info["default_samplerate"]))))
except Exception:
    print(48000)
PY
}

AUDIO_DEVICE="$(resolve_audio_device)"
AUDIO_CHANNELS="${PUMPKIN_AUDIO_CHANNELS:-1}"
AUDIO_SAMPLE_RATE="$(resolve_audio_sample_rate)"
STT_DURATION="${PUMPKIN_STT_DURATION:-3.0}"
STT_MODEL="${PUMPKIN_STT_MODEL:-small}"
STT_DEVICE="${PUMPKIN_STT_DEVICE:-cuda}"
STT_COMPUTE_TYPE="${PUMPKIN_STT_COMPUTE_TYPE:-int8}"
STT_SPEECH_THRESHOLD="${PUMPKIN_STT_SPEECH_THRESHOLD:-500.0}"
STT_SPEECH_START_BLOCKS="${PUMPKIN_STT_SPEECH_START_BLOCKS:-2}"
# Must remain below the 500 RMS speech-start default. The previous 850 value
# was invalid and got silently replaced with 250, making endpoint detection slow.
STT_END_THRESHOLD="${PUMPKIN_STT_END_THRESHOLD:-425.0}"
STT_END_CEILING_RATIO="${PUMPKIN_STT_END_CEILING_RATIO:-0.97}"
STT_SILENCE_DURATION="${PUMPKIN_STT_SILENCE_DURATION:-0.8}"
# max_duration is a fail-safe only. Normal turns should stop via end-of-speech
# detection, so keep enough room for a long natural cafe order.
STT_MAX_DURATION="${PUMPKIN_STT_MAX_DURATION:-10.0}"
# Confirmation/slot answers are short. Bound only those turns so ambient noise
# cannot hold the microphone open for the full long-order fail-safe.
STT_CONFIRMATION_MAX_DURATION="${PUMPKIN_STT_CONFIRMATION_MAX_DURATION:-3.5}"
STT_START_TIMEOUT="${PUMPKIN_STT_START_TIMEOUT:-15.0}"
# TTSNode publishes done only after audio playback has exited, so the extra
# acoustic-tail guard can be short. 0.15s keeps the anti-echo interlock while
# allowing natural immediate replies such as "따뜻하게" without losing them.
STT_POST_TTS_GUARD="${PUMPKIN_STT_POST_TTS_GUARD:-0.15}"

# ROS2 infers command-line parameter types from their lexical form. Values such
# as "150" are therefore parsed as INTEGER and fail when the node declares the
# parameter as DOUBLE. Normalize all floating-point STT settings so integer-like
# environment overrides (for example PUMPKIN_STT_SPEECH_THRESHOLD=150) remain
# valid and are passed to rclpy as "150.0".
normalize_ros_double() {
  local value="$1"
  if [[ "${value}" =~ ^[-+]?[0-9]+$ ]]; then
    printf "%s.0" "${value}"
  else
    printf "%s" "${value}"
  fi
}

STT_SPEECH_THRESHOLD="$(normalize_ros_double "${STT_SPEECH_THRESHOLD}")"
STT_END_THRESHOLD="$(normalize_ros_double "${STT_END_THRESHOLD}")"
STT_END_CEILING_RATIO="$(normalize_ros_double "${STT_END_CEILING_RATIO}")"
STT_SILENCE_DURATION="$(normalize_ros_double "${STT_SILENCE_DURATION}")"
STT_MAX_DURATION="$(normalize_ros_double "${STT_MAX_DURATION}")"
STT_CONFIRMATION_MAX_DURATION="$(normalize_ros_double "${STT_CONFIRMATION_MAX_DURATION}")"
STT_START_TIMEOUT="$(normalize_ros_double "${STT_START_TIMEOUT}")"
STT_POST_TTS_GUARD="$(normalize_ros_double "${STT_POST_TTS_GUARD}")"
# Use ALSA directly by default. paplay ignores alsa_device and can silently send
# speech to a different PulseAudio sink even though playback exits successfully.
TTS_PLAYER="${PUMPKIN_TTS_PLAYER:-aplay}"
TTS_ALSA_DEVICE="${PUMPKIN_TTS_ALSA_DEVICE:-plughw:0,0}"
TTS_VOLUME="${PUMPKIN_TTS_VOLUME:-+0%}"
ENABLE_VISION="${PUMPKIN_ENABLE_VISION:-0}"
ENABLE_FACE_RECOGNITION="${PUMPKIN_ENABLE_FACE_RECOGNITION:-0}"
ENABLE_FACE_DISPLAY="${PUMPKIN_ENABLE_FACE_DISPLAY:-1}"
FACE_SERIAL_PORT="${PUMPKIN_ESP32_PORT:-auto}"
CAMERA_INDEX=""

mkdir -p "${LOG_DIR}"
rm -f "${LOG_DIR}"/*.log "${NLU_READY_FILE}" "${STT_READY_FILE}"

declare -A PIDS
declare -A LOGS

print_log_tail() {
  local name="$1"
  local log_file="${LOGS[$name]:-${LOG_DIR}/${name}.log}"
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

wait_for_vision_ready() {
  local name="$1"
  local timeout_seconds="$2"
  local log_file="${LOGS[$name]:-${LOG_DIR}/${name}.log}"
  local attempts=$(( timeout_seconds * 4 ))
  local attempt=0

  echo "[WAIT] ${name} 실제 카메라 프레임 확인 중... 최대 ${timeout_seconds}초"
  while (( attempt < attempts )); do
    assert_alive "${name}" || return 1

    # Presence probe is emitted only after vision_node has read and processed a
    # real camera frame, so it is a stronger readiness signal than process-alive.
    if [[ -f "${log_file}" ]] && grep -q "Presence probe:" "${log_file}"; then
      echo "[READY] ${name} camera_index=${CAMERA_INDEX} - 실제 프레임 처리 확인"
      return 0
    fi

    if [[ -f "${log_file}" ]] && grep -Eq \
      "Camera [0-9]+ open failed|Camera frame read failed" "${log_file}"; then
      echo "[FAIL] ${name}가 카메라를 열거나 프레임을 읽지 못했습니다." >&2
      print_log_tail "${name}"
      return 1
    fi

    sleep 0.25
    ((attempt += 1))
  done

  echo "[FAIL] ${name}에서 실제 카메라 프레임을 확인하지 못했습니다." >&2
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

"${CORE_PYTHON_BIN}" - <<'PY'
import sys
import ctranslate2
import faster_whisper
import rclpy
import robot_controller

print(f"Core/STT Python: {sys.executable}")
print(f"robot_controller path: {robot_controller.__file__}")
print(f"faster-whisper path: {faster_whisper.__file__}")
print(f"CTranslate2 path: {ctranslate2.__file__}")
print(f"CTranslate2 CUDA devices: {ctranslate2.get_cuda_device_count()}")
if ctranslate2.get_cuda_device_count() < 1:
    raise SystemExit("코어 가상환경 CTranslate2에서 CUDA GPU를 찾지 못했습니다.")
PY

if [[ "${ENABLE_FACE_DISPLAY}" == "1" ]]; then
  "${CORE_PYTHON_BIN}" - <<'PY'
import serial
from robot_face.jetson import FaceController

print(f"pyserial: {serial.__version__}")
print(f"ESP32 face controller: {FaceController.__module__}.{FaceController.__name__}")
PY
fi

"${CORE_PYTHON_BIN}" - "${AUDIO_DEVICE}" "${AUDIO_CHANNELS}" "${AUDIO_SAMPLE_RATE}" <<'PY'
import sys
import sounddevice as sd

device_index = int(sys.argv[1])
channels = int(sys.argv[2])
sample_rate = int(sys.argv[3])
device = None if device_index < 0 else device_index

info = sd.query_devices(device, "input")
sd.check_input_settings(
    device=device,
    channels=channels,
    samplerate=sample_rate,
    dtype="int16",
)

print(
    "STT audio input: "
    f"device={device_index}, name={info['name']}, "
    f"channels={channels}/{info['max_input_channels']}, "
    f"sample_rate={sample_rate}"
)
PY

(
  unset LD_LIBRARY_PATH
  source /opt/ros/humble/setup.bash
  source "${WORKSPACE}/install/setup.bash"
  PYTHONNOUSERSITE=1 "${NLU_PYTHON_BIN}" - <<'PY'
import sys
import rclpy
import torch

print(f"NLU Python: {sys.executable}")
print(f"PyTorch: {torch.__version__}")
print(f"PyTorch path: {torch.__file__}")
print(f"PyTorch CUDA build: {torch.version.cuda}")
print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("NLU 가상환경 PyTorch에서 CUDA GPU를 찾지 못했습니다.")
x = torch.ones((16, 16), device="cuda", dtype=torch.float16)
y = x @ x
torch.cuda.synchronize()
print(f"NLU CUDA tensor test: device={y.device}, value={float(y[0, 0].item())}")
PY
)

if [[ "${ENABLE_VISION}" == "1" ]]; then
  if [[ ! -f "${CAMERA_RESOLVER}" ]]; then
    echo "[FAIL] 카메라 탐색기를 찾을 수 없습니다: ${CAMERA_RESOLVER}" >&2
    exit 1
  fi

  echo "[CHECK] USB camera stable discovery + real-frame preflight"
  if ! CAMERA_INDEX="$("${CORE_PYTHON_BIN}" "${CAMERA_RESOLVER}")"; then
    echo "[FAIL] 사용 가능한 카메라를 찾지 못했습니다. ROS 파이프라인을 시작하지 않습니다." >&2
    exit 1
  fi
  export PUMPKIN_CAMERA_INDEX="${CAMERA_INDEX}"
  echo "[OK] camera preflight passed: index=${CAMERA_INDEX}"
fi

echo
echo "Starting pumpkin ROS nodes sequentially..."
echo "core_python=${CORE_PYTHON_BIN}"
echo "face_recognition=${ENABLE_FACE_RECOGNITION}"
echo "nlu_python=${NLU_PYTHON_BIN}"
echo "audio_device=${AUDIO_DEVICE}, audio_channels=${AUDIO_CHANNELS}, audio_sample_rate=${AUDIO_SAMPLE_RATE}, stt_model=${STT_MODEL}, stt_device=${STT_DEVICE}, stt_compute_type=${STT_COMPUTE_TYPE}, nlu_device=${PUMPKIN_NLU_DEVICE}, vision=${ENABLE_VISION}, camera_index=${CAMERA_INDEX:-disabled}, face_display=${ENABLE_FACE_DISPLAY}, face_port=${FACE_SERIAL_PORT}"
echo "tts_audio: player=${TTS_PLAYER}, alsa_device=${TTS_ALSA_DEVICE}, volume=${TTS_VOLUME}"
echo "stt_vad: start=${STT_SPEECH_THRESHOLD}, start_blocks=${STT_SPEECH_START_BLOCKS}, end=${STT_END_THRESHOLD}, end_ceiling_ratio=${STT_END_CEILING_RATIO}, silence=${STT_SILENCE_DURATION}s, max=${STT_MAX_DURATION}s, confirm_max=${STT_CONFIRMATION_MAX_DURATION}s, start_timeout=${STT_START_TIMEOUT}s, post_tts_guard=${STT_POST_TTS_GUARD}s"
echo "logs=${LOG_DIR}"

if [[ "${ENABLE_TEGRASTATS}" == "1" ]] && command -v tegrastats >/dev/null 2>&1; then
  start_process tegrastats tegrastats --interval "${TEGRASTATS_INTERVAL_MS}"
fi

# Launch the consolidated production ROS modules explicitly.
start_process decision_node "${CORE_PYTHON_BIN}" -m robot_controller.decision_node
start_process response_manager_node "${CORE_PYTHON_BIN}" -m robot_controller.response_manager_node
if [[ "${ENABLE_FACE_RECOGNITION}" == "1" ]]; then
  start_process face_personalization_node \
    "${CORE_PYTHON_BIN}" -m robot_controller.face_personalization_node
fi
start_process action_node "${CORE_PYTHON_BIN}" -m robot_controller.action_node

if [[ "${ENABLE_FACE_DISPLAY}" == "1" ]]; then
  start_process face_display_node \
    "${CORE_PYTHON_BIN}" -m robot_controller.face_display_node --ros-args \
    -p serial_port:="${FACE_SERIAL_PORT}"
else
  echo "face_display_node disabled (set PUMPKIN_ENABLE_FACE_DISPLAY=1 to enable)"
fi

start_process tts_node \
  "${CORE_PYTHON_BIN}" -m robot_controller.tts_node --ros-args \
  -p player:="${TTS_PLAYER}" \
  -p alsa_device:="${TTS_ALSA_DEVICE}" \
  -p volume:="${TTS_VOLUME}"

sleep 2
for node in decision_node response_manager_node action_node tts_node; do
  assert_alive "${node}"
done
if [[ "${ENABLE_FACE_DISPLAY}" == "1" ]]; then
  assert_alive face_display_node
fi
if [[ "${ENABLE_FACE_RECOGNITION}" == "1" ]]; then
  assert_alive face_personalization_node
fi

# NLU and STT must be completely ready before vision is allowed to detect a
# customer. Otherwise a person can trigger the greeting while the microphone
# subscriber is still loading, creating a long dead gap after the greeting.
start_process nlu_node bash "${NLU_RUNNER}"
wait_for_ready_file nlu_node "${NLU_READY_FILE}" "${STARTUP_TIMEOUT}"

sleep 2
start_process stt_node \
  "${CORE_PYTHON_BIN}" -m robot_controller.stt_node --ros-args \
  -p audio_device:="${AUDIO_DEVICE}" \
  -p channels:="${AUDIO_CHANNELS}" \
  -p sample_rate:="${AUDIO_SAMPLE_RATE}" \
  -p model_size:="${STT_MODEL}" \
  -p model_device:="${STT_DEVICE}" \
  -p compute_type:="${STT_COMPUTE_TYPE}" \
  -p speech_threshold:="${STT_SPEECH_THRESHOLD}" \
  -p speech_start_blocks:="${STT_SPEECH_START_BLOCKS}" \
  -p end_threshold:="${STT_END_THRESHOLD}" \
  -p adaptive_end_ceiling_ratio:="${STT_END_CEILING_RATIO}" \
  -p silence_duration:="${STT_SILENCE_DURATION}" \
  -p max_duration:="${STT_MAX_DURATION}" \
  -p confirmation_max_duration:="${STT_CONFIRMATION_MAX_DURATION}" \
  -p start_timeout:="${STT_START_TIMEOUT}" \
  -p post_tts_guard_sec:="${STT_POST_TTS_GUARD}"
wait_for_ready_file stt_node "${STT_READY_FILE}" "${STARTUP_TIMEOUT}"

if [[ "${ENABLE_VISION}" == "1" ]]; then
  echo "[START] vision after NLU/STT readiness"
  start_process vision_node "${CORE_PYTHON_BIN}" -m robot_controller.vision_node
  wait_for_vision_ready vision_node "${VISION_STARTUP_TIMEOUT}"
else
  echo "vision_node disabled (set PUMPKIN_ENABLE_VISION=1 to enable)"
fi

echo
echo "Pumpkin ROS voice pipeline is READY."
echo "Flow: STT(VAD) -> NLU -> Decision -> Response Manager -> Action -> TTS/Face LCD -> STT"
echo "Multimodal: NOD/SHAKE confirmation + ONE_FINGER..FIVE_FINGERS quantity=1..5"
echo "NLU: saved_models/structure_b_item_query_decoder (${PUMPKIN_NLU_DEVICE}, ${NLU_PYTHON_BIN})"
echo "STT runtime: robot_controller.stt_node"
echo "Decision runtime: robot_controller.decision_node"
echo "Vision runtime: robot_controller.vision_node"
echo "STT: faster-whisper ${STT_MODEL} (${STT_DEVICE}/${STT_COMPUTE_TYPE}, ${CORE_PYTHON_BIN})"
echo "TTS: ${TTS_PLAYER} -> ${TTS_ALSA_DEVICE}"
if [[ "${ENABLE_FACE_DISPLAY}" == "1" ]]; then
  echo "Face LCD: /robot_action.face -> ESP32 USB Serial (${FACE_SERIAL_PORT}) -> ILI9488"
  echo "Face log: ${LOG_DIR}/face_display_node.log"
fi
if [[ "${ENABLE_TEGRASTATS}" == "1" && -f "${LOG_DIR}/tegrastats.log" ]]; then
  echo "Memory log: ${LOG_DIR}/tegrastats.log"
  echo "Watch memory: tail -f ${LOG_DIR}/tegrastats.log"
fi
echo "Press Ctrl+C to stop all nodes."
echo

set +e
wait -n
status=$?
set -e

echo "[FAIL] ROS 노드 또는 모니터링 프로세스 중 하나가 종료되었습니다. exit=${status}" >&2
for name in "${!PIDS[@]}"; do
  if ! kill -0 "${PIDS[$name]}" 2>/dev/null; then
    echo "종료된 프로세스: ${name}" >&2
    print_log_tail "${name}"
  fi
done
exit "${status}"