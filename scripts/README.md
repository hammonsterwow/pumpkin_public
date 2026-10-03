# scripts

실물 로봇 시연과 서비스 실행에 필요한 런처 및 하드웨어 보조 스크립트만 모아 둔 폴더입니다.

## 가장 중요한 실행 명령

Jetson Orin Nano에서 로봇, 5인치 고객 화면, 음성·비전·NLU·TTS·모터 파이프라인을 한 번에 실행합니다.

```bash
cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

현재 실물 시연의 기본 진입점은 **`run_robot_with_monitor.sh`** 입니다.

## 실행 흐름

```text
run_robot_with_monitor.sh
        │
        ├─ apps/monitor-web/server.py
        ├─ Chromium kiosk
        │
        └─ run_robot_interaction_demo.sh
                    │
                    ├─ order_submission_node
                    ├─ motor_controller_node
                    │
                    └─ run_ros_voice_nodes.sh
                                │
                                ├─ STT
                                ├─ NLU
                                ├─ Decision
                                ├─ Response Manager
                                ├─ Action
                                ├─ TTS
                                ├─ Face LCD
                                └─ Vision
```

## 현재 파일

| 파일 | 역할 | 직접 실행 여부 |
|---|---|---|
| `run_robot_with_monitor.sh` | 5인치 모니터와 전체 실물 로봇 파이프라인을 함께 시작하는 최종 시연 런처 | **주 실행 파일** |
| `run_robot_interaction_demo.sh` | ROS 대화 파이프라인, 주문 전송 노드, PCA9685 모터 제어 노드를 묶어 실행 | 보통 직접 실행하지 않음 |
| `run_ros_voice_nodes.sh` | STT → NLU → Decision → Response → Action → TTS/Face/Vision ROS2 노드를 순차 실행 | 내부 실행 |
| `run_nlu_node_cuda.sh` | Jetson CUDA 환경에서 NLU 노드를 실행 | 내부 실행 |
| `resolve_camera_device.py` | 사용 가능한 USB 카메라를 탐색하고 실제 프레임 입력이 가능한 장치를 선택 | 내부 실행 |
| `stop_robot_interaction_nodes.sh` | 이전 실행에서 남은 Pumpkin ROS/모니터 프로세스를 종료 | 문제 발생 시 사용 |
| `servo_power_on.sh` | PCA9685 서보 전원 시퀀스를 ON 방향으로 수행 | 하드웨어 점검 시 사용 |
| `servo_power_off.sh` | PCA9685 서보 전원 시퀀스를 OFF 방향으로 수행 | 하드웨어 점검 시 사용 |
| `pca9685/servo_power_sequence.py` | 서보 전원 ON/OFF 시퀀스 실제 구현 | 위 두 스크립트에서 호출 |
| `run_web_api.sh` | FastAPI 웹 API 서버 실행 | 웹 API 단독 실행 시 사용 |
| `run_customer_mobile.ps1` | Windows PowerShell에서 고객용 모바일 앱 개발 서버 실행 | 앱 개발 시 사용 |

## 시연 전 확인

```bash
cd ~/pumpkin_public
git pull
source .venv/bin/activate
source /opt/ros/humble/setup.bash

cd ros2_ws
colcon build --packages-select robot_controller --symlink-install
source install/setup.bash

cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

`run_robot_with_monitor.sh` 내부에서 기본 시연 설정을 적용하므로 일반적인 현장 시연에서는 환경변수를 길게 붙이지 않아도 됩니다.

## 종료

실행 중인 터미널에서 `Ctrl+C`를 누르면 통합 런처가 하위 프로세스를 함께 종료합니다.

이전 실행 프로세스가 남아 중복 음성이나 중복 ROS 노드가 발생하면 다음을 실행합니다.

```bash
bash scripts/stop_robot_interaction_nodes.sh
```

## 폴더 정리 원칙

이 폴더에는 **실제 실행·시연·하드웨어 운용에 필요한 스크립트만 유지**합니다.

학습용 데이터 생성, 일회성 실험, 디버그 터미널, 과거 테스트 런처, PC/macOS 전용 레거시 스크립트는 포함하지 않습니다.
