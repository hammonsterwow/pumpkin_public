#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ROOT_DIR}/ros2_ws"
PYTHON_BIN="${PUMPKIN_DEMO_WEB_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
PORT="${PUMPKIN_DEMO_WEB_PORT:-8765}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python 가상환경을 찾을 수 없습니다: ${PYTHON_BIN}" >&2
  exit 1
fi

source /opt/ros/humble/setup.bash
if [[ -f "${WORKSPACE}/install/setup.bash" ]]; then
  source "${WORKSPACE}/install/setup.bash"
else
  echo "ROS2 workspace가 아직 빌드되지 않았습니다." >&2
  echo "먼저 bash scripts/run_robot_interaction_demo.sh 를 실행해 robot_controller를 빌드하세요." >&2
  exit 1
fi

cd "${ROOT_DIR}"
export PYTHONNOUSERSITE=1
export PUMPKIN_PROJECT_ROOT="${ROOT_DIR}"
export PUMPKIN_DEMO_WEB_HOST="${PUMPKIN_DEMO_WEB_HOST:-0.0.0.0}"
export PUMPKIN_DEMO_WEB_PORT="${PORT}"

"${PYTHON_BIN}" - <<'PY'
missing = []
for module in ("fastapi", "uvicorn", "rclpy", "sensor_msgs"):
    try:
        __import__(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")
if missing:
    raise SystemExit(
        "시연웹 실행 의존성 확인에 실패했습니다:\n- " + "\n- ".join(missing)
        + "\nFastAPI/uvicorn은 api/requirements.txt를 설치하고, ROS 환경을 source 했는지 확인하세요."
    )
print("[CHECK] FastAPI / uvicorn / ROS2 / sensor_msgs OK")
PY

echo
echo "============================================================"
echo " Pumpkin 시연웹"
echo "============================================================"
echo "Jetson 역할 : ROS Topic 구독 + 640px JPEG stream 전달"
echo "Laptop 역할 : 화면 렌더링 + LOG 메모리 보관"
echo "Port        : ${PORT}"
echo

JETSON_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -n "${JETSON_IP}" ]]; then
  echo "노트북 브라우저에서 접속: http://${JETSON_IP}:${PORT}"
else
  echo "노트북 브라우저에서 접속: http://<JETSON_IP>:${PORT}"
fi

echo
echo "종료: Ctrl+C"
echo "============================================================"
echo

exec "${PYTHON_BIN}" "${ROOT_DIR}/apps/demo-web/server.py"
