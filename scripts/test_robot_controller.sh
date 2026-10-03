#!/usr/bin/env bash
set -eo pipefail

PROJECT_ROOT="${PUMPKIN_PROJECT_ROOT:-$HOME/pumpkin}"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
ROS_WS="${PROJECT_ROOT}/ros2_ws"

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "오류: ROS2 setup 파일을 찾을 수 없습니다: ${ROS_SETUP}" >&2
  exit 1
fi

if [[ ! -d "${ROS_WS}" ]]; then
  echo "오류: ROS2 workspace를 찾을 수 없습니다: ${ROS_WS}" >&2
  exit 1
fi

# Ubuntu의 system pytest와 ~/.local의 최신 pytest plugin이 섞이면
# '_pytest.scope' 같은 내부 API 버전 충돌이 발생할 수 있다.
# robot_controller 회귀 테스트는 외부 pytest plugin을 필요로 하지 않으므로
# user-site 패키지와 자동 plugin 로딩을 모두 차단한다.
export PYTHONNOUSERSITE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# ROS setup 스크립트는 일부 변수를 미리 정의하지 않은 채 참조할 수 있다.
# 따라서 이 실행기는 nounset(set -u)을 사용하지 않는다.
# shellcheck disable=SC1090
source "${ROS_SETUP}"

if [[ -f "${ROS_WS}/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "${ROS_WS}/install/setup.bash"
fi

if ! python3 -s -c 'import pytest; print("pytest", pytest.__version__)'; then
  echo "오류: system Python에서 pytest를 불러오지 못했습니다." >&2
  echo "설치 명령: sudo apt install -y python3-pytest" >&2
  exit 1
fi

cd "${ROS_WS}"

python3 -s -m pytest -q \
  src/robot_controller/test/test_dialogue_responsibility_split.py \
  src/robot_controller/test/test_hardware_action_contract.py \
  src/robot_controller/test/test_order_handoff.py \
  src/robot_controller/test/test_dialogue_pipeline_scenarios.py
