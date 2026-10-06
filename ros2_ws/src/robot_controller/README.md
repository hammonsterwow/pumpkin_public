# Pumpkin ROS2 Robot Controller

Jetson Orin Nano에서 음성·비전 입력을 받아 주문 의미를 해석하고, 대화 상태를 판단한 뒤 TTS·LCD·목·팔 동작과 Cloud 주문 전송까지 연결하는 ROS2 패키지입니다.

## 전체 구조

```text
Camera / Microphone
      ↓
Vision / STT
      ↓
NLU
      ↓
Decision + Order Dialogue
      ↓
Response Manager
      ↓
Action
      ├─ TTS
      ├─ Face LCD
      ├─ Head / Arm Motor
      └─ Customer Monitor

주문 종료
      ↓
Order Submission Node
      ↓
Cloud Relay / POS
```

얼굴 인식이 활성화된 경우:

```text
Realtime Face Recognition
→ /face_recognition_result
→ Face Personalization
→ Firestore profile + active preorder
→ /customer_context
→ Decision
```

## 주요 노드

| 노드 | 역할 |
|---|---|
| `stt_node` | Faster-Whisper 기반 음성 인식과 VAD |
| `nlu_node` | koELECTRA Item Query Decoder 추론과 명시 슬롯 추출 |
| `decision_node` | 주문 FSM, 누락 슬롯, 수정·취소·추가주문·확인 처리 |
| `response_manager_node` | Decision 결과를 실제 한국어 응답으로 렌더링 |
| `action_node` | 표정·고개·팔·STT 재개 시점을 결정 |
| `tts_node` | 음성 출력 및 `/tts/status` 발행 |
| `vision_node` | 사용자 존재, 고개·손 제스처와 시연 카메라 프레임 처리 |
| `face_display_node` | `/robot_action.face`를 ESP32 얼굴 LCD에 적용 |
| `motor_controller_node` | PCA9685 기반 목·팔 명령 실행 |
| `face_personalization_node` | 등록 고객·사전주문 정보를 Decision에 전달 |
| `order_submission_node` | 종료된 ROBOT 주문을 Cloud Relay에 1회 제출 |

## 핵심 모듈

- `menu_policy.py`: `config/menu_catalog.json` 기반 메뉴·온도·수량 정책
- `order_schema.py`: NLU와 후속 발화를 공통 주문 구조로 정규화
- `dialogue_slots.py`: 짧은 후속 답변에서 명시된 메뉴·온도·수량 추출
- `order_dialogue_manager.py`: 현재 주문 상태와 수정/추가 흐름 관리
- `nlu_postprocess.py`, `multi_item_span_grounding.py`: NLU 결과 보정
- `head_gesture_recognizer.py`, `hand_quantity_gesture.py`: 비언어 입력 처리
- `arm_motion.py`, `motor_driver.py`: 실제 서보 동작과 PCA9685 제어
- `preorder.py`: Cloud Relay 사전주문 조회·상태 변경

## 주요 ROS Topic

| Topic | 역할 |
|---|---|
| `/stt/trigger` | Action → STT 녹음 제어 |
| `/stt/status` | STT 상태 |
| `/voice_text` | 사용자 발화 텍스트 |
| `/intent_result` | NLU 구조화 결과 |
| `/decision_result` | 대화/FSM 판단 |
| `/response_result` | 실제 응답 문장 |
| `/robot_action` | 표정·화면·고개·팔 추상 행동 |
| `/tts/status` | TTS 재생 상태 |
| `/human_presence` | 사용자 존재 여부 |
| `/user/head_gesture` | NOD / SHAKE |
| `/face_recognition_result` | 실시간 얼굴 인식 결과 |
| `/customer_context` | 등록 고객·사전주문 context |

## NLU

운영 NLU 코드는 저장소 루트의 [`nlu/`](../../../nlu/)를 사용합니다.

```text
nlu/saved_models/structure_b_item_query_decoder/
```

체크포인트의 label map은 시작 시 현재 메뉴 정책과 비교하며 불일치하면 NLU READY 이전에 실행을 중단합니다.

누락된 값은 임의로 채우지 않고 Decision 단계가 현재 `waiting_for` 항목을 기준으로 다시 질문합니다. ICE 전용 메뉴처럼 서비스 정책으로 단일 선택이 확정된 경우에만 정책값을 적용합니다.

## STT/TTS 턴 제어

정상 대화에서는 TTS가 끝난 뒤에만 다음 STT를 엽니다.

```text
Decision
→ Response
→ Action
→ TTS speaking
→ TTS done
→ /stt/trigger
```

음성 인식의 `empty`, `no_speech`, `too_quiet`, `rejected` 같은 회복 가능한 실패는 현재 주문을 보존한 채 다시 질문합니다. 오디오 장치나 STT runtime 오류는 자동 반복을 중단하고 오류 상태를 발행합니다.

## 실행 환경

Jetson에서는 두 Python 환경을 분리합니다.

| 환경 | 역할 |
|---|---|
| `.venv` | ROS2 코어, STT, TTS, Vision, 하드웨어 |
| `.venv-nlu` | JetPack 호환 CUDA PyTorch NLU |

상세 환경은 [`JETSON_RUNTIME_README.md`](../../../JETSON_RUNTIME_README.md)를 참고합니다.

## 빌드

```bash
cd ~/pumpkin_public/ros2_ws
source /opt/ros/humble/setup.bash

colcon build \
  --packages-select robot_controller \
  --symlink-install

source install/setup.bash
```

## 실물 로봇 실행

권장 진입점:

```bash
cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

이 런처는 5인치 고객 화면을 먼저 시작한 뒤 `run_robot_interaction_demo.sh`를 통해 주문 전송 노드, PCA9685 모터 노드와 음성/비전 대화 파이프라인을 실행합니다.

5인치 화면 없이 로봇 상호작용만 실행:

```bash
bash scripts/run_robot_interaction_demo.sh
```

ROS 음성·비전 파이프라인만 실행:

```bash
bash scripts/run_ros_voice_nodes.sh
```

실제 스크립트 구성은 [`scripts/README.md`](../../../scripts/README.md)를 기준으로 합니다.

## 주요 환경 변수

| 변수 | 기본/역할 |
|---|---|
| `PUMPKIN_CORE_PYTHON` | 코어/STT Python |
| `PUMPKIN_NLU_PYTHON` | NLU CUDA Python |
| `PUMPKIN_NLU_DEVICE` | NLU device, 통합 환경은 CUDA |
| `PUMPKIN_STT_DEVICE` | STT device |
| `PUMPKIN_AUDIO_DEVICE` | 마이크 장치; 미설정 시 탐색 |
| `PUMPKIN_ENABLE_VISION` | Vision 활성화 |
| `PUMPKIN_ENABLE_FACE_RECOGNITION` | 얼굴인식/개인화 활성화 |
| `PUMPKIN_ENABLE_FACE_DISPLAY` | ESP32 얼굴 LCD 활성화 |
| `PUMPKIN_MOTOR_BACKEND` | 실물 런처 기본 `pca9685` |
| `PUMPKIN_ENABLE_ARM` | 팔 동작 활성화 |
| `PUMPKIN_LOG_DIR` | 기본 `/tmp/pumpkin-logs` |

## 로그

기본 로그 디렉터리:

```text
/tmp/pumpkin-logs/
```

예:

```bash
tail -f /tmp/pumpkin-logs/nlu_node.log
tail -f /tmp/pumpkin-logs/stt_node.log
tail -f /tmp/pumpkin-logs/motor_controller_node.log
tail -f /tmp/pumpkin-logs/order_submission_node.log
```

## 종료

통합 런처를 실행한 터미널에서 `Ctrl+C`를 사용합니다. 이전 실행 프로세스가 남아 있으면 저장소 루트에서:

```bash
bash scripts/stop_robot_interaction_nodes.sh
```

하드웨어 전원 투입·차단 순서는 [`hardware/SERVO_POWER_ON_OFF_MANUAL.md`](../../../hardware/SERVO_POWER_ON_OFF_MANUAL.md)를 따릅니다.
