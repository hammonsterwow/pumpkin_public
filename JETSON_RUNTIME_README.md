# Jetson Runtime Environment

Jetson Orin Nano에서는 ROS2/STT 환경과 NLU CUDA PyTorch 환경을 **서로 다른 Python 가상환경으로 분리**해서 사용합니다.

## 왜 가상환경을 분리하는가

기존 공통 `.venv`에는 ROS2 노드, Faster-Whisper, CTranslate2가 설치되어 있습니다. 반면 koELECTRA NLU는 JetPack 6.2.2 / L4T R36.5 환경에서 동작하는 CUDA PyTorch 2.8.0이 필요합니다.

두 환경의 CUDA 라이브러리 요구사항이 달라 하나의 가상환경에 합치면 CPU 전용 PyTorch가 설치되거나 `LD_LIBRARY_PATH` 충돌이 발생할 수 있습니다.

## 가상환경 역할

| 경로 | 역할 | 주요 패키지 |
|---|---|---|
| `.venv` | ROS2 코어 노드와 STT 실행 | `rclpy`, `faster-whisper`, `ctranslate2` |
| `.venv-nlu` | NLU 노드의 CUDA 추론 | `torch 2.8.0`, `transformers`, koELECTRA 모델 |

`.venv-nlu`는 로컬 실행 환경이므로 Git에 커밋하지 않습니다.

## Jetson 기준 환경

- Jetson Orin Nano
- JetPack 6.2.2
- L4T R36.5
- CUDA 12.6
- ROS2 Humble
- `.venv-nlu`: PyTorch 2.8.0 CUDA 12.6 빌드

## 실행 방법

```bash
cd ~/pumpkin

PUMPKIN_ENABLE_VISION=0 \
PUMPKIN_NLU_DEVICE=cuda \
PUMPKIN_STT_DEVICE=cuda \
PUMPKIN_STT_COMPUTE_TYPE=int8 \
bash scripts/run_ros_voice_nodes.sh
```

스크립트는 다음 순서로 동작합니다.

1. `.venv`에서 CTranslate2 CUDA 장치 인식 여부 확인
2. `.venv-nlu`에서 PyTorch CUDA 텐서 연산 확인
3. ROS2 코어 노드 실행
4. `.venv-nlu`에서 NLU 노드 실행
5. NLU 준비 완료 후 `.venv`에서 STT 노드 실행
6. `tegrastats` 메모리 로그 저장

정상 시작 시 아래 메시지가 출력됩니다.

```text
CTranslate2 CUDA devices: 1
PyTorch CUDA available: True
NLU CUDA tensor test: device=cuda:0
[READY] nlu_node
[READY] stt_node
Pumpkin ROS voice pipeline is READY.
```

## NLU 단독 ROS2 확인

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin/ros2_ws/install/setup.bash
ros2 topic echo /intent_result
```

다른 터미널에서:

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin/ros2_ws/install/setup.bash

ros2 topic pub --once \
  /voice_text \
  std_msgs/msg/String \
  "{data: '아이스 아메리카노 두 잔 주세요'}"
```

현재 확인된 범위는 `/voice_text → CUDA NLU 추론 → /intent_result`입니다. 마이크 입력부터 STT, FSM, TTS, 로봇 동작까지 이어지는 전체 서비스 흐름은 별도 통합 테스트가 필요합니다.

## 로그

```text
/tmp/pumpkin-logs/nlu_node.log
/tmp/pumpkin-logs/stt_node.log
/tmp/pumpkin-logs/decision_node.log
/tmp/pumpkin-logs/action_node.log
/tmp/pumpkin-logs/tts_node.log
/tmp/pumpkin-logs/tegrastats.log
```

메모리 확인:

```bash
tail -f /tmp/pumpkin-logs/tegrastats.log
```

## 주의사항

공통 `requirements.txt`에 있는 PyTorch를 Jetson NLU 환경에 그대로 설치하지 않습니다.

다음 명령은 `.venv-nlu`에서 실행하지 마세요.

```bash
pip install torch
pip install torch==2.2.2
pip install -r requirements.txt
```

NLU 실행 시 `LD_LIBRARY_PATH` 충돌을 피하기 위해 `scripts/run_nlu_node_cuda.sh`가 환경 변수를 초기화하고 ROS2 환경만 다시 구성합니다.
