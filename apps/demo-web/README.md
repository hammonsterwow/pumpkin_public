# 시연웹 (`apps/demo-web`)

로봇의 실시간 카메라 입력과 ROS2 처리 흐름을 시연용으로 보여주는 독립 웹 화면입니다. 기존 관리자 웹(`web/`)이나 고객 앱(`apps/customer-mobile`)과는 별개입니다.

## 화면 구성

- **ROBOT VISION**: 로봇 카메라 영상을 왼쪽 영역 전체에 표시합니다.
  - 기존 `vision_node`의 MediaPipe FaceMesh 추론 결과에서 실제 고개 자세 계산에 사용하는 6개 landmark만 재사용해 영상에 표시합니다.
  - `NOD`, `SHAKE`, 사람 감지 상태를 실시간으로 표시합니다.
- **ROBOT BRAIN**: 오른쪽 영역에서 최근 처리 결과를 시간순으로 보여줍니다.
  - 최신 이벤트를 가장 크게 표시하고, 직전 이벤트는 작고 연하게 남겨 처리 흐름을 눈으로 따라갈 수 있게 합니다.
  - 최근 최대 5개 이벤트를 약 12초간 유지한 뒤 오래된 이벤트부터 자동으로 제거합니다.
  - `ORDER UNDERSTANDING`: 메뉴 / 온도 / 수량만 간단히 표시
  - `DECISION`: 내부 FSM 이름 대신 사람이 이해하기 쉬운 판단 문장 표시
  - `ROBOT ACTION`: 표정 / 고개 / 팔 동작 표시
- **음성 상태**: 실제 `/stt/status`, `/tts/status`를 이용해 말을 해야 하는 시점을 표시합니다.
  - `LISTENING · 지금 말씀해주세요.`: 고객 발화를 기다리는 상태
  - `LISTENING · 말씀을 듣고 있습니다.`: 고객 음성을 감지해 받고 있는 상태
  - `SPEECH RECOGNITION · 음성을 인식하고 있습니다.`: Faster-Whisper 처리 상태
  - `ROBOT SPEAKING · 로봇이 말하고 있습니다.`: TTS 출력 상태
- **하단 자막**: STT 결과(USER)와 TTS 응답(ROBOT)을 크게 표시합니다.
- **LOG**: 오른쪽 상단 버튼에서 현재 시연 중 수신한 이벤트를 시간순으로 확인할 수 있습니다. 로그는 브라우저/메모리에만 유지하며 별도 파일이나 DB에 기록하지 않습니다.

## 성능 원칙

시연웹이 실제 로봇 동작에 영향을 주지 않도록 다음 원칙을 사용합니다.

1. 카메라를 두 번 열지 않습니다. 기존 `vision_node`가 읽은 프레임을 재사용합니다.
2. MediaPipe를 두 번 실행하지 않습니다. 기존 FaceMesh 추론에서 사용 중인 6개 landmark 좌표만 표시용으로 재사용합니다.
3. `/demo/camera/compressed`에 구독자가 없으면 JPEG 인코딩 자체를 수행하지 않습니다.
4. 기본 영상은 폭 640px, 8 FPS, JPEG quality 68로 제한합니다.
5. ROS 상태 데이터는 WebSocket 하나로 변경 시점에만 전달합니다.
6. 웹 UI 렌더링, 최근 이벤트 유지, LOG 목록 보관은 Jetson이 아니라 노트북 브라우저가 담당합니다.
7. 프론트엔드는 React/Vite 없이 HTML/CSS/JavaScript만 사용해 빌드 과정과 런타임 부담을 줄였습니다.

필요하면 환경 변수로 영상 전송량을 조절할 수 있습니다.

```bash
export PUMPKIN_DEMO_STREAM_FPS=8
export PUMPKIN_DEMO_STREAM_WIDTH=640
export PUMPKIN_DEMO_STREAM_JPEG_QUALITY=68
```

# 시연웹 실행 방법

## 0. 최신 `main` 받기

시연웹 기능이 `main`에 합쳐진 이후에는 Jetson에서 다음 명령으로 최신 코드를 받습니다.

```bash
cd ~/pumpkin
git switch main
git pull origin main
```

처음 시연웹을 받은 직후에는 `robot_controller` 변경 사항과 `sensor_msgs` 의존성이 함께 반영되므로 로봇 실행 스크립트의 기본 빌드 과정을 한 번 수행하는 것을 권장합니다.

## 1. 터미널 1 - 실제 로봇 전체 실행

Jetson에서 먼저 실제 로봇 파이프라인을 실행합니다.

```bash
cd ~/pumpkin
bash scripts/run_robot_interaction_demo.sh
```

이 터미널은 카메라, STT, NLU, Decision, Response Manager, Robot Action, TTS, 얼굴 LCD, 목 모터 등 실제 상호작용 흐름을 실행합니다.

## 2. 터미널 2 - 시연웹 실행

새 터미널을 열어 다음 명령을 실행합니다.

```bash
cd ~/pumpkin
bash scripts/run_demo_web.sh
```

정상 실행되면 터미널에 다음과 같이 노트북에서 접속할 주소가 출력됩니다.

```text
노트북 브라우저에서 접속: http://<JETSON_IP>:8765
```

예시:

```text
http://192.168.0.15:8765
```

## 3. 노트북에서 접속

Jetson과 같은 네트워크에 연결된 노트북의 Chrome 등 브라우저에서 위 주소를 엽니다.

```text
http://<JETSON_IP>:8765
```

시연웹은 노트북에서 렌더링되며 Jetson은 ROS 데이터와 압축 카메라 프레임을 전달합니다.

## 4. 시연 중 말을 하는 시점

오른쪽 ROBOT BRAIN 상단의 실시간 상태를 기준으로 말합니다.

```text
LISTENING
지금 말씀해주세요.
```

가 표시될 때 고객이 주문 또는 응답을 말하면 됩니다.

말하기 시작하면 다음과 같이 바뀝니다.

```text
LISTENING
말씀을 듣고 있습니다.
```

이후 음성 변환 중에는 다음 상태가 표시됩니다.

```text
SPEECH RECOGNITION
음성을 인식하고 있습니다.
```

로봇이 TTS를 재생하는 동안에는 다음과 같이 표시되며, 이때는 고객 발화를 기다리는 상태가 아닙니다.

```text
ROBOT SPEAKING
로봇이 말하고 있습니다.
```

## 5. 종료

각 터미널에서 `Ctrl+C`로 종료합니다.

```text
터미널 2: 시연웹 종료
터미널 1: 로봇 전체 파이프라인 종료
```

일반적으로 시연웹을 먼저 종료한 뒤 로봇 파이프라인을 종료하면 됩니다.

## 실행 오류 확인

### `scripts/run_demo_web.sh`가 없다고 나오는 경우

현재 브랜치와 최신 코드를 확인합니다.

```bash
cd ~/pumpkin
git branch --show-current
git switch main
git pull origin main
ls scripts | grep run_demo_web
```

정상이면 다음 파일명이 표시됩니다.

```text
run_demo_web.sh
```

### FastAPI / uvicorn 의존성 오류

```bash
cd ~/pumpkin
source .venv/bin/activate
pip install -r api/requirements.txt
```

### ROS2 workspace가 빌드되지 않았다는 오류

먼저 터미널 1에서 다음 스크립트를 한 번 실행해 `robot_controller`를 빌드합니다.

```bash
cd ~/pumpkin
bash scripts/run_robot_interaction_demo.sh
```

### 시연웹은 열리지만 카메라가 나오지 않는 경우

로봇 실행 터미널에서 `vision_node`가 정상 실행 중인지 확인합니다.

```bash
ros2 node list | grep vision_node
ros2 topic info /demo/camera/compressed
```

시연웹이 연결된 상태에서는 `/demo/camera/compressed`에 subscriber가 있어야 합니다.

## 시연웹이 읽는 ROS Topic

| Topic | 사용 위치 |
|---|---|
| `/demo/camera/compressed` | ROBOT VISION 영상 |
| `/human_presence` | 고객 감지 표시 |
| `/user/head_gesture` | NOD / SHAKE 표시 및 DECISION |
| `/stt/status` | LISTENING / SPEECH RECOGNITION 상태 및 LOG |
| `/voice_text` | USER 자막 |
| `/intent_result` | ORDER UNDERSTANDING |
| `/decision_result` | DECISION |
| `/response_result` | ROBOT 자막 |
| `/robot_action` | ROBOT ACTION |
| `/tts/status` | ROBOT SPEAKING 상태 및 LOG |
| `/face/recognition` | 등록 고객 인식 |
| `/demo/preorder` | 사전 주문 표시용 선택 Topic |

### 사전 주문 연동

현재 시연웹은 사전 주문 시스템이 연결될 수 있도록 `/demo/preorder` JSON Topic을 선택적으로 구독합니다. 퍼블리셔가 없어도 시연웹 동작에는 영향이 없습니다.

예상 payload 예시는 다음 정도입니다.

```json
{
  "items": [
    {"menu": "아메리카노", "temperature": "ICE", "quantity": 1}
  ],
  "status": "준비 중"
}
```

실제 사전 주문 서버 연동 시 해당 주문 데이터가 확정되는 지점에서 이 Topic을 publish하면 같은 ROBOT BRAIN 화면에 `ORDER UNDERSTANDING` 이벤트로 표시됩니다.
