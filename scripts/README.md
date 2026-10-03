# Pumpkin 테스트 스크립트

웹사이트 없이 ROS2 주문 대화를 터미널에서 시험할 수 있습니다.

## 사전 준비

```bash
cd ~/pumpkin
git checkout main
git pull

cd ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_controller --symlink-install
source install/setup.bash
```

## ROS 음성 파이프라인 실행

### Jetson Orin Nano

첫 번째 터미널에서 실행합니다.

```bash
cd ~/pumpkin
PUMPKIN_NLU_DEVICE=cuda bash scripts/run_ros_voice_nodes.sh
```

### 일반 PC Ubuntu 22.04

PC에는 ROS2 Humble과 프로젝트의 `.venv`, `.venv-nlu` 환경이 준비되어 있어야 합니다. 새 스크립트는 NVIDIA GPU 사용 가능 여부를 자동 확인하고, CUDA가 없으면 NLU와 STT를 CPU 모드로 전환합니다.

첫 번째 터미널:

```bash
cd ~/pumpkin
bash scripts/run_ros_voice_nodes_pc.sh
```

장치를 직접 지정할 수도 있습니다.

```bash
# CPU 강제 실행
PUMPKIN_NLU_DEVICE=cpu \
PUMPKIN_STT_DEVICE=cpu \
PUMPKIN_STT_COMPUTE_TYPE=int8 \
bash scripts/run_ros_voice_nodes_pc.sh

# NVIDIA CUDA GPU 강제 실행
PUMPKIN_NLU_DEVICE=cuda \
PUMPKIN_STT_DEVICE=cuda \
PUMPKIN_STT_COMPUTE_TYPE=float16 \
bash scripts/run_ros_voice_nodes_pc.sh
```

두 번째 터미널:

```bash
cd ~/pumpkin
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/terminal_chat.py
```

디버그 출력:

```bash
python3 scripts/terminal_chat.py --debug
```

> Windows와 macOS에서는 ROS2 Humble 및 Linux 오디오 의존성 차이 때문에 직접 실행을 지원하지 않습니다. Windows 사용자는 Ubuntu 22.04 듀얼부트 또는 별도 Ubuntu PC를 권장합니다. WSL2는 마이크·스피커와 ROS2 네트워크 설정을 추가로 구성해야 합니다.

이 스크립트는 현재 VAD 기반 `stt_node`, NLU, Decision, Response Manager, Action, TTS를 실행합니다.

## 음성 대화 테스트

두 번째 터미널에서 실행합니다.

```bash
cd ~/pumpkin
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/voice_terminal_chat.py
```

이 프로그램은 마이크 녹음이나 Whisper 추론을 직접 구현하지 않습니다.

```text
/‌human_presence 또는 /stt/trigger
→ ROS stt_node
→ 현재 Energy VAD로 발화 시작 감지
→ 침묵 구간 감지 후 자동 녹음 종료
→ Faster-Whisper
→ /voice_text
→ NLU → Decision → Response Manager → Action → TTS
→ TTS done 이후 /stt/trigger start
```

따라서 녹음을 시작하기 위해 엔터를 누르지 않습니다. 프로그램 실행 후 안내에 따라 바로 말하면 되며, 종료할 때만 `Ctrl+C`를 사용합니다.

기본 실행은 가상 고객 접근 신호를 보내 로봇 인사부터 시작합니다.

```text
Pumpkin ROS VAD 음성 대화 테스트
[시작] 가상 고객 접근 신호를 보냅니다.
로봇 > 안녕하세요. 주문 도와드릴게요.
[TTS] 재생 완료
[STT] 듣는 중입니다. 지금 말씀하세요.
[STT] 음성을 감지했습니다. 말이 끝나면 VAD가 자동으로 녹음을 종료합니다.

나(STT) > 아메리카노 하나요
로봇 > 아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?
```

### 인사 없이 STT부터 시작

```bash
python3 scripts/voice_terminal_chat.py --start-mode listen
```

### 실제 vision_node의 고객 감지를 기다리기

```bash
PUMPKIN_ENABLE_VISION=1 bash scripts/run_ros_voice_nodes.sh
```

PC에서는 다음과 같이 실행합니다.

```bash
PUMPKIN_ENABLE_VISION=1 bash scripts/run_ros_voice_nodes_pc.sh
```

다른 터미널에서:

```bash
python3 scripts/voice_terminal_chat.py --start-mode none
```

### 다음 손님 자동 시뮬레이션

주문 종료 후 `NEXT_CUSTOMER_READY`가 되면 3초 뒤 다음 고객 접근을 자동으로 발생시킵니다.

```bash
python3 scripts/voice_terminal_chat.py --auto-next-customer
```

지연 시간을 바꿀 수 있습니다.

```bash
python3 scripts/voice_terminal_chat.py \
  --auto-next-customer \
  --next-customer-delay 5
```

### 전체 JSON 확인

```bash
python3 scripts/voice_terminal_chat.py --debug
```

`/decision_result`, `/response_result`, `/robot_action`의 JSON을 함께 출력합니다.

## 텍스트 대화 테스트

음성 인식을 제외하고 NLU 이후 흐름만 시험하려면 기존 프로그램을 사용합니다.

```bash
python3 scripts/terminal_chat.py
```

텍스트 프로그램은 사용자가 입력한 문장을 `/voice_text`로 직접 발행합니다. STT와 VAD까지 확인하려면 반드시 `voice_terminal_chat.py`를 사용합니다.

## 문제 확인

### ROS 파이프라인 연결 오류

```bash
ros2 node list
```

다음 노드가 보여야 합니다.

```text
/stt_node
/nlu_node
/decision_node
/response_manager_node
/action_node
/tts_node
```

Topic 확인:

```bash
ros2 topic info /stt/trigger
ros2 topic info /stt/status
ros2 topic info /voice_text
ros2 topic info /response_result
```

### 마이크 장치 변경

Jetson:

```bash
PUMPKIN_AUDIO_DEVICE=1 bash scripts/run_ros_voice_nodes.sh
```

PC:

```bash
PUMPKIN_AUDIO_DEVICE=1 bash scripts/run_ros_voice_nodes_pc.sh
```

장치 목록은 다음 명령으로 확인합니다.

```bash
cd ~/pumpkin
source .venv/bin/activate
python - <<'PY'
import sounddevice as sd
print(sd.query_devices())
PY
```

### VAD가 음성을 감지하지 못함

STT 로그를 확인합니다.

```bash
tail -f /tmp/pumpkin-logs/stt_node.log
```

주요 상태:

```text
listening       발화 시작 대기
speech_detected VAD가 음성 시작 감지
transcribing    Faster-Whisper 인식 중
done            /voice_text 발행 완료
no_speech       제한 시간 동안 발화 미감지
too_quiet       녹음 음량 부족
empty           텍스트 결과 없음
rejected        신뢰하기 어려운 짧은 결과 제외
```
