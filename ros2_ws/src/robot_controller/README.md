# Pumpkin ROS2 Robot Controller

Jetson Orin Nano에서 음성 주문, NLU, 대화 상태 관리, 로봇 행동 결정을 연결하는 ROS2 패키지입니다.

현재 운영 파이프라인은 다음 원칙을 사용합니다.

```text
STT = 음성을 텍스트로 변환
NLU = 문장의 의도와 주문 항목을 구조화
Decision = 주문 상태와 다음 질문을 결정
Action = TTS·LCD·고개·팔의 추상 행동을 생성
Hardware = 추상 행동을 실제 장치 명령으로 실행
```

NLU 모델은 `nlu_node`에서 한 번만 로딩합니다. 웹과 FastAPI는 별도 모델을 실행하지 않고 실제 ROS Topic 결과를 관찰합니다.

---

## 전체 실행 흐름

```text
사용자 음성 또는 웹 텍스트 입력
        ↓
stt_node 또는 FastAPI
        ↓
/voice_text
        ↓
nlu_node
- Structure B Item Query Decoder
- 명시적 짧은 답변 추출
        ↓
/intent_result
        ↓
decision_node
- FSM 상태 관리
- 항목별 누락 슬롯 질문
- 수정·취소·재시작·확인 처리
        ↓
/decision_result
        ↓
action_node
- 표정·화면·고개·팔 명령 생성
- TTS 완료 후 STT 시작 제어
        ↓
/robot_action
        ↓
tts_node 및 향후 하드웨어 실행 노드
```

비전 기능을 활성화하면 다음 흐름이 추가됩니다.

```text
vision_node
→ /human_presence
→ decision_node
→ START_ORDER 인사
```

---

## 실행 환경 분리

Jetson에서는 CUDA 라이브러리 충돌을 줄이기 위해 두 Python 환경을 분리합니다.

| 환경 | 역할 | 주요 라이브러리 |
|---|---|---|
| `.venv` | ROS2 코어, STT, Decision, Action, TTS | `rclpy`, `faster-whisper`, `ctranslate2` |
| `.venv-nlu` | NLU 전용 | CUDA PyTorch, Transformers |

`scripts/run_ros_voice_nodes.sh`는 다음 순서로 노드를 올립니다.

```text
Decision · Action · TTS
→ NLU CUDA 모델 로딩 및 READY 확인
→ STT CUDA 모델 로딩 및 READY 확인
```

NLU와 STT를 순차적으로 로딩하여 Jetson 통합 메모리의 순간 사용량을 줄입니다.

> `scripts/check_jetson_nlu.sh`를 `.venv`에서 단독 실행하면 PyTorch CUDA가 비활성으로 보일 수 있습니다. 실제 운영 NLU는 `.venv-nlu`에서 실행되며, 전체 실행 스크립트가 별도로 CUDA tensor test를 수행합니다.

---

## 패키지 구성

```text
ros2_ws/src/robot_controller/
├── README.md
├── package.xml
├── setup.py
├── resource/
├── robot_controller/
│   ├── stt_node.py
│   ├── nlu_node.py
│   ├── decision_node.py
│   ├── action_node.py
│   ├── tts_node.py
│   ├── vision_node.py
│   ├── face_personalization_node.py
│   ├── dialogue_slots.py
│   ├── menu_policy.py
│   └── order_schema.py
└── test/
    ├── test_menu_policy.py
    ├── test_order_schema.py
    ├── test_dialogue_flow.py
    └── test_dialogue_pipeline_scenarios.py
```

### 주요 파일 역할

| 파일 | 역할 |
|---|---|
| `stt_node.py` | Faster-Whisper로 음성을 텍스트로 변환 |
| `nlu_node.py` | Structure B NLU 모델을 로딩하고 `/intent_result` 발행 |
| `decision_node.py` | FSM, 누락 슬롯 질문, 주문 병합·수정·확인·취소 처리 |
| `action_node.py` | Decision 결과를 TTS·표정·화면·고개·팔 명령으로 변환 |
| `tts_node.py` | TTS 재생 및 `/tts/status` 발행 |
| `vision_node.py` | Haar Cascade 얼굴 검출 후 `/human_presence` 발행 |
| `dialogue_slots.py` | 짧은 후속 발화에서 명시된 메뉴·온도·수량 추출 |
| `menu_policy.py` | 메뉴·별칭·허용 온도·수량·NLU label map의 단일 기준 |
| `order_schema.py` | NLU와 후속 답변을 같은 주문 스키마로 정규화·검증 |

---

## ROS Topic

| Topic | 타입 | 발행 → 구독 | 역할 |
|---|---|---|---|
| `/stt/trigger` | `std_msgs/String` | Action → STT | `start` 수신 시 녹음 시작 |
| `/stt/status` | `std_msgs/String` | STT → Action/Web | `ready`, `recording`, `transcribing`, `done`, 오류 상태 |
| `/voice_text` | `std_msgs/String` | STT/Web → NLU | 사용자 발화 텍스트 |
| `/intent_result` | `std_msgs/String` | NLU → Decision/Web | NLU JSON 결과 |
| `/decision_result` | `std_msgs/String` | Decision → Action/Web | 대화 판단 JSON |
| `/robot_action` | `std_msgs/String` | Action → TTS/Web/Hardware | 추상 로봇 행동 JSON |
| `/tts/text` | `std_msgs/String` | 수동 테스트 → TTS | TTS 단독 시험용 문장 |
| `/tts/status` | `std_msgs/String` | TTS → Action/Decision | `ready`, `speaking`, `done`, 오류 상태 |
| `/human_presence` | `std_msgs/Bool` | Vision → Decision | 사용자 접근 여부 |
| `/head_gesture` | `std_msgs/String` | Vision → 후속 처리 | 현재 비언어 신호용 Topic |

현재 주요 구조화 메시지는 `std_msgs/String` 안의 JSON을 사용합니다. ROS2 커스텀 메시지는 추후 적용 대상입니다.

---

## NLU 모델과 출력

운영 모델은 다음 하나만 사용합니다.

```text
nlu/saved_models/structure_b_item_query_decoder/
```

모델 구조와 학습 방법은 저장소의 [`nlu/README.md`](../../../nlu/README.md)를 참고합니다.

`nlu_node`는 모델 출력을 주문 구조의 기준으로 유지합니다. 파이썬 규칙은 Item Query Decoder의 `items` 전체를 교체하지 않습니다.

짧은 후속 답변에서 직접 표현된 값만 별도 `explicit_slots`로 추가합니다.

```json
{
  "text": "따뜻하게요",
  "explicit_slots": {
    "menu": null,
    "temperature": "HOT",
    "quantity": null
  }
}
```

이 값은 `decision_node`가 특정 슬롯을 질문 중일 때만 대화 문맥과 함께 사용합니다.

---

## 단일 메뉴 정책

메뉴와 옵션 정책의 기준 파일은 다음입니다.

```text
robot_controller/menu_policy.py
```

현재 지원 메뉴는 다음과 같습니다.

| 메뉴 | 허용 온도 | 온도 누락 처리 |
|---|---|---|
| 아메리카노 | `ICE`, `HOT` | 온도 질문 |
| 카페라떼 | `ICE`, `HOT` | 온도 질문 |
| 바닐라라떼 | `ICE`, `HOT` | 온도 질문 |
| 레몬에이드 | `ICE` | `ICE` 자동 적용 |
| 딸기스무디 | `ICE` | `ICE` 자동 적용 |

수량 범위는 `1~20`입니다.

다음 표현도 표준값으로 정규화합니다.

```text
레모네이드 → 레몬에이드
라테 → 카페라떼
아이스·냉으로 → ICE
따뜻하게·온으로 → HOT
한 잔~스무 잔 → 1~20
```

`nlu_node` 시작 시 체크포인트의 `menu`, `temperature`, `quantity` label map을 이 정책과 비교합니다. 정책과 모델이 다르면 NLU READY 이전에 실행을 중단합니다.

```text
NLU label maps match the shared menu policy
NLU node ready
```

새 메뉴 추가 절차는 [`nlu/README.md`의 초코라떼 예시](../../../nlu/README.md#새-메뉴-추가-예시-초코라떼)를 참고합니다.

---

## 주문 스키마

`order_schema.py`는 모델 결과와 짧은 후속 답변을 같은 구조로 변환합니다.

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "intent": "ORDER",
  "confidence": 0.9999,
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "temperature": "ICE",
      "quantity": 2,
      "missing_slots": [],
      "validation_errors": []
    }
  ],
  "order_status": "VALID",
  "needs_reprompt": false
}
```

### 검증 항목

- 지원하지 않는 메뉴
- 지원하지 않는 온도 표현
- 메뉴에서 허용하지 않는 온도
- 수량 1~20 범위
- 메뉴·온도·수량 누락
- 최대 3개 주문 항목

정책 위반이나 정규화 실패는 `validation_errors`에 기록합니다.

---

## 대화 상태와 `waiting_for`

`decision_node`는 다음 주요 상태를 사용합니다.

```text
IDLE
→ GREETING
→ ORDER_LISTEN
→ ASK_MENU / ASK_QUANTITY / ASK_TEMPERATURE
→ ORDER_CONFIRM
→ ORDER_CORRECTION 또는 ORDER_COMPLETE
→ IDLE
```

누락 슬롯을 질문할 때는 슬롯 이름만 저장하지 않고 정확한 주문 항목을 함께 저장합니다.

```json
{
  "waiting_for": {
    "item_id": 1,
    "slot": "temperature"
  }
}
```

이 구조를 사용해 `"따뜻하게요"` 같은 후속 답변을 질문 대상 항목에만 병합합니다.

### 항목별 질문 예시

```text
사용자: 아메리카노랑 라떼 하나씩 주세요.
로봇: 아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?
사용자: 따뜻하게요.
로봇: 카페라떼는 아이스로 드릴까요, 따뜻하게 드릴까요?
사용자: 아이스로요.
로봇: 따뜻한 아메리카노 1잔, 아이스 카페라떼 1잔 맞으신가요?
```

주문 항목은 `menu → quantity → temperature` 순서로 확인하며, 한 항목을 완성한 뒤 다음 항목으로 이동합니다.

---

## 모든 항목에 적용하는 답변

다음 표현은 현재 주문의 모든 항목에 명시된 온도 또는 수량을 적용합니다.

```text
둘 다
모두
전부
각각
```

예시:

```text
사용자: 아메리카노랑 라떼 하나씩 주세요.
로봇: 아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?
사용자: 둘 다 아이스로요.
→ 두 메뉴 모두 ICE 적용
```

`둘 다`는 현재 주문 항목이 정확히 두 개일 때만 적용합니다. 메뉴 구조는 모델이 만든 복수 `items`를 그대로 유지합니다.

---

## 수정·취소·재시작

### 복수 주문 수정

복수 주문에서 수정 대상 메뉴가 없으면 첫 번째 항목을 임의로 수정하지 않습니다.

```text
사용자: 아이스로 바꿔주세요.
로봇: 어떤 메뉴를 변경할까요? 메뉴 이름과 변경 내용을 함께 말씀해 주세요.
```

### 취소

```text
취소
주문 취소
그만할게요
```

현재 주문과 대화 상태를 초기화하고 `IDLE`로 복귀합니다.

### 처음부터 다시 주문

```text
다시 주문
처음부터
새로 주문
```

새 `session_id`를 발급하고 `ORDER_LISTEN`으로 돌아갑니다.

---

## 재질문 횟수

기본 재질문 제한은 다음과 같습니다.

| 종류 | 기본 제한 | 초과 시 처리 |
|---|---:|---|
| NLU 저신뢰도·이해 실패 | 2회 | 세 번째 실패에서 처음부터 재주문 요청 |
| 슬롯 답변 실패 | 2회 | 세 번째 실패에서 현재 주문 초기화 |
| STT 실패 | 2회 | 재시도 중단 및 화면 안내 |

ROS 파라미터:

```text
max_nlu_reprompts
max_slot_retries
max_stt_retries
```

---

## TTS 완료 후 STT 실행

`action_node`는 고정 시간만 기다린 뒤 STT를 시작하지 않습니다.

정상 흐름은 다음과 같습니다.

```text
Decision 발행
→ Action 발행
→ TTS speaking
→ TTS done
→ /stt/trigger = start
```

`done`만 먼저 수신하거나 아직 `speaking`을 확인하지 않았다면 STT를 시작하지 않습니다.

TTS 상태 이벤트가 오지 않는 예외 상황에서는 기본 12초 timeout 후 fallback으로 STT를 시작합니다.

주문 확정 후에는 완료 TTS가 끝날 때까지 `ORDER_COMPLETE`를 유지하고, `/tts/status = done` 수신 후 `IDLE`로 복귀합니다.

---

## Action 출력

`action_node`는 `/decision_result`를 다음 추상 행동으로 변환합니다.

```json
{
  "decision": "CONFIRM_ORDER",
  "tts": "아이스 아메리카노 2잔 맞으신가요?",
  "face": "SMILE",
  "display": "ORDER_CONFIRM",
  "display_text": "아이스 아메리카노 2잔 맞으신가요?",
  "head": "LOOK_USER",
  "arm": "WAIT",
  "priority": "NORMAL",
  "source_reason": "all_slots_filled"
}
```

| 필드 | 의미 |
|---|---|
| `decision` | Decision Node의 판단 결과 |
| `tts` | 사용자에게 말할 문장 |
| `face` | LCD 표정 상태 |
| `display` | 화면 상태 또는 페이지 |
| `display_text` | 화면에 표시할 문구 |
| `head` | 추상 목 동작 |
| `arm` | 추상 팔 동작 |
| `priority` | `LOW`, `NORMAL`, `HIGH` |
| `source_reason` | 판단 근거 코드 |

### 주요 Decision

| Decision | 의미 |
|---|---|
| `START_ORDER` | 사용자 감지 후 인사 |
| `ASK_MENU` | 메뉴 질문 |
| `ASK_QUANTITY` | 수량 질문 |
| `ASK_TEMPERATURE` | 온도 질문 |
| `REPROMPT` | 발화 재질문 |
| `CONFIRM_ORDER` | 전체 주문 확인 |
| `ORDER_CONFIRMED` | 주문 확정 |
| `MODIFY_ORDER` | 주문 수정 요청 |
| `CANCEL_ORDER` | 주문 취소 |
| `REORDER_REQUEST` | 처음부터 다시 주문 요청 |
| `OUT_OF_POLICY` | 지원하지 않는 주문 |
| `GUIDE_CUSTOMER` | 매장 안내 |
| `PAYMENT_GUIDE` | 결제 안내 |

서보 각도, PWM 값, 이미지 경로 같은 하드웨어 세부값은 Action Node에 넣지 않습니다. 실제 장치 노드가 추상 명령을 하드웨어 값으로 변환해야 합니다.

---

## 빌드

```bash
cd ~/pumpkin/ros2_ws
source /opt/ros/humble/setup.bash

colcon build \
  --packages-select robot_controller \
  --symlink-install

source install/setup.bash
```

코드 수정 후에는 다시 빌드하거나 `--symlink-install` 환경을 사용합니다.

---

## 전체 실행

저장소 루트에서 실행합니다.

```bash
cd ~/pumpkin

bash scripts/check_jetson_nlu.sh

PUMPKIN_NLU_DEVICE=cuda \
bash scripts/run_pos_with_nlu.sh
```

실행 구성:

1. Decision Node
2. Action Node
3. TTS Node
4. NLU Node
5. STT Node
6. 선택적 Vision Node
7. FastAPI
8. React 관리자 웹
9. `tegrastats` 메모리 모니터링

브라우저 주소:

```text
http://JETSON_IP:3000
```

로그 위치:

```text
/tmp/pumpkin-logs/
```

메모리 로그 확인:

```bash
tail -f /tmp/pumpkin-logs/tegrastats.log
```

---

## 주요 환경 변수

| 환경 변수 | 기본값 | 역할 |
|---|---|---|
| `PUMPKIN_CORE_PYTHON` | `.venv/bin/python` | 코어·STT Python |
| `PUMPKIN_NLU_PYTHON` | `.venv-nlu/bin/python` | NLU 전용 Python |
| `PUMPKIN_NLU_DEVICE` | `cuda` | NLU 장치 |
| `PUMPKIN_STT_DEVICE` | `cuda` | STT 장치 |
| `PUMPKIN_STT_COMPUTE_TYPE` | `int8` | Faster-Whisper 연산 형식 |
| `PUMPKIN_STT_MODEL` | `small` | Faster-Whisper 모델 |
| `PUMPKIN_AUDIO_DEVICE` | `0` | 마이크 장치 번호 |
| `PUMPKIN_ENABLE_VISION` | `0` | Vision Node 실행 여부 |
| `PUMPKIN_STARTUP_TIMEOUT` | `180` | 노드 READY 대기 시간 |
| `PUMPKIN_ENABLE_TEGRASTATS` | `1` | 메모리 모니터링 여부 |

예시:

```bash
PUMPKIN_AUDIO_DEVICE=2 \
PUMPKIN_ENABLE_VISION=1 \
PUMPKIN_NLU_DEVICE=cuda \
bash scripts/run_pos_with_nlu.sh
```

---

## 자동 테스트

저장소 루트 또는 ROS2 워크스페이스에서 실행합니다.

```bash
cd ~/pumpkin/ros2_ws

PYTHONPATH=src/robot_controller \
python3 -m pytest \
  src/robot_controller/test/test_menu_policy.py \
  src/robot_controller/test/test_order_schema.py \
  src/robot_controller/test/test_dialogue_flow.py \
  src/robot_controller/test/test_dialogue_pipeline_scenarios.py \
  -q
```

### 테스트 범위

- 메뉴·온도·수량 정규화
- 차가운 메뉴의 ICE 기본값
- NLU 체크포인트 label map 정책 검사
- `waiting_for.item_id` 대상 병합
- 다중 주문 항목별 질문
- `둘 다 아이스로요` 공통 적용
- 복수 주문 수정 대상 확인
- 취소 및 처음부터 다시 주문
- 슬롯 답변 실패 3회
- NLU 저신뢰도 3회
- TTS `speaking → done` 이후 STT 시작
- 주문 완료 TTS 이후 `IDLE` 복귀

`test_dialogue_pipeline_scenarios.py`는 가짜 predictor와 메모리 내 publisher를 사용하지만 다음 실제 노드 콜백을 순서대로 실행합니다.

```text
nlu_node.voice_callback
→ decision_node.intent_callback
→ action_node.decision_callback
→ TTS status callback
```

따라서 대화 제어 회귀 테스트이며, 실제 NLU 모델 정확도·DDS 통신·마이크·스피커 성능 검증을 대체하지 않습니다.

---

## 수동 Topic 테스트

먼저 ROS 환경을 적용합니다.

```bash
cd ~/pumpkin/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
```

### 텍스트 주문 입력

```bash
ros2 topic pub --once \
  /voice_text std_msgs/msg/String \
  "{data: '아이스 아메리카노 두 잔 주세요'}"
```

### TTS 단독 실행

```bash
ros2 topic pub --once \
  /tts/text std_msgs/msg/String \
  "{data: '안녕하세요. 주문을 도와드릴게요.'}"
```

### STT 녹음 시작

```bash
ros2 topic pub --once \
  /stt/trigger std_msgs/msg/String \
  "{data: 'start'}"
```

### 마이크 장치 확인

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

---

## 문제 확인 순서

### NLU가 READY 되지 않을 때

```bash
tail -n 100 /tmp/pumpkin-logs/nlu_node.log
```

확인 항목:

- `.venv-nlu`에서 `torch.cuda.is_available() == True`
- `best_model.pt`와 `tokenizer/` 존재
- 체크포인트 label map과 `menu_policy.py` 일치

### STT가 READY 되지 않을 때

```bash
tail -n 100 /tmp/pumpkin-logs/stt_node.log
```

확인 항목:

- CTranslate2 CUDA device 수
- 마이크 장치 번호
- `PUMPKIN_STT_COMPUTE_TYPE=int8`

### TTS 후 STT가 시작되지 않을 때

다음 Topic을 확인합니다.

```bash
ros2 topic echo /tts/status
ros2 topic echo /stt/trigger
```

정상 순서:

```text
speaking
→ done
→ start
```

### 전체 메모리 확인

```bash
tail -f /tmp/pumpkin-logs/tegrastats.log
```

Jetson에서 NLU와 STT를 동시에 실행할 때는 시스템 RAM, swap, GPU 사용률을 함께 확인합니다.
