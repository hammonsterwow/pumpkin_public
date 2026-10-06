# Pumpkin 시연 웹

실제 로봇 카메라와 ROS2 이벤트를 브라우저에서 보여주는 시연용 웹입니다. POS(`apps/pos-web`)와 5인치 고객 화면(`apps/monitor-web`)과는 목적이 다릅니다.

## 표시 내용

- **ROBOT VISION**: 기존 `vision_node`의 압축 카메라 프레임과 고개 제스처
- **ORDER UNDERSTANDING**: 최신 NLU 주문 항목
- **DECISION**: 현재 대화 판단
- **ROBOT ACTION**: 표정·고개·팔 행동
- **STT/TTS 상태**: 사용자가 말할 타이밍과 로봇 발화 상태
- **자막/LOG**: 사용자 STT와 로봇 응답의 최근 이벤트

시연 웹은 카메라나 MediaPipe를 별도로 다시 실행하지 않고 기존 ROS2 결과를 구독합니다.

## 성능 원칙

- 카메라를 중복으로 열지 않습니다.
- 기존 Vision 결과를 재사용합니다.
- 카메라 구독자가 없으면 JPEG 전송 작업을 하지 않습니다.
- 기본 스트림은 640 px, 8 FPS, JPEG quality 68입니다.
- 상태는 WebSocket으로 변경 시점에 전달합니다.

필요하면 다음 환경 변수로 조정합니다.

```bash
export PUMPKIN_DEMO_STREAM_FPS=8
export PUMPKIN_DEMO_STREAM_WIDTH=640
export PUMPKIN_DEMO_STREAM_JPEG_QUALITY=68
export PUMPKIN_DEMO_WEB_PORT=8765
```

## 실행

### 1. 로봇 파이프라인

첫 터미널:

```bash
cd ~/pumpkin_public
git switch main
git pull --ff-only
bash scripts/run_robot_interaction_demo.sh
```

### 2. 시연 웹

두 번째 터미널:

```bash
cd ~/pumpkin_public
source .venv/bin/activate
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 apps/demo-web/server.py
```

기본 주소:

```text
http://<JETSON_IP>:8765
```

Jetson과 같은 네트워크의 노트북 브라우저에서 접속합니다.

## 주요 ROS Topic

| Topic | 표시 용도 |
|---|---|
| `/demo/camera/compressed` | 카메라 영상 |
| `/human_presence` | 고객 감지 |
| `/user/head_gesture` | NOD / SHAKE |
| `/stt/status` | 음성 입력·인식 상태 |
| `/voice_text` | USER 자막 |
| `/intent_result` | 주문 이해 |
| `/decision_result` | 대화 판단 |
| `/response_result` | ROBOT 자막 |
| `/robot_action` | 표정·고개·팔 행동 |
| `/tts/status` | 로봇 발화 상태 |
| `/face/recognition` | 등록 고객 인식 |
| `/demo/preorder` | 선택적 사전주문 표시 |

`/demo/preorder` 퍼블리셔가 없어도 시연 웹의 기본 동작에는 영향이 없습니다.

## 종료

시연 웹 터미널과 로봇 실행 터미널에서 각각 `Ctrl+C`로 종료합니다.

## 문제 확인

카메라가 보이지 않으면:

```bash
ros2 node list | grep vision_node
ros2 topic info /demo/camera/compressed
```

시연 웹 Python 의존성이 부족하면:

```bash
source .venv/bin/activate
pip install -r api/requirements.txt
```

ROS2 workspace를 갱신한 뒤에는:

```bash
cd ~/pumpkin_public/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_controller --symlink-install
```
