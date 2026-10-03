# 현재 주문 흐름 문제점 및 수정 계획

작성 기준: `main` 브랜치의 현재 ROS2 주문 파이프라인 코드

관련 파일:

- `ros2_ws/src/robot_controller/robot_controller/vision_node.py`
- `ros2_ws/src/robot_controller/robot_controller/stt_node.py`
- `ros2_ws/src/robot_controller/robot_controller/nlu_node.py`
- `ros2_ws/src/robot_controller/robot_controller/model_wrapper.py`
- `ros2_ws/src/robot_controller/robot_controller/decision_node.py`
- `ros2_ws/src/robot_controller/robot_controller/action_node.py`
- `api/ros_bridge.py`
- `docs/order_dialogue_rules.md`

---

## 1. 문서 목적

현재 구현된 주문 흐름을 팀원들이 동일하게 이해하고, 설계 문서와 실제 코드의 차이를 확인하며, 이후 수정 작업의 우선순위와 완료 기준을 정하기 위한 문서이다.

이 문서에서는 다음 내용을 정리한다.

1. 현재 실제 동작 흐름
2. 현재 코드의 문제점
3. 각 문제의 영향
4. 수정 방향 및 해결 방안
5. 우선순위별 작업 목록
6. 테스트 시나리오와 완료 기준

---

## 2. 현재 실제 주문 흐름

현재 코드의 전체 흐름은 다음과 같다.

```text
카메라에서 얼굴 감지
    ↓
/human_presence = True
    ↓
decision_node: IDLE → ORDER_LISTEN
    ↓
START_ORDER 발행
    ↓
action_node: 인사 동작 및 TTS 요청
    ↓ 3초 후
/stt/trigger = start
    ↓
마이크로 4초 녹음
    ↓
faster-whisper STT
    ↓
/voice_text 발행
    ↓
NLU 모델 분석
    ↓
/intent_result 발행
    ↓
decision_node에서 의도와 통합 confidence 평가
    ├─ confidence < 0.75 또는 needs_reprompt=True → REPROMPT
    ├─ ORDER → ORDER_CONFIRM
    ├─ CANCEL → IDLE
    ├─ MODIFY → ORDER_LISTEN
    └─ GUIDE/PAYMENT/UNKNOWN → 각 응답
                ↓
        주문 확인 질문
                ↓ 4초 후
        마이크로 다시 4초 녹음
                ↓
        확인 응답 판별
        ├─ 긍정 → ORDER_COMPLETE
        └─ 부정 → ORDER_LISTEN
```

현재 큰 파이프라인 자체는 연결되어 있다.

```text
비전 → 의사결정 → 음성 녹음 → STT → NLU → 의사결정 → 로봇 응답
```

다만 상태 초기화, 재질문, 빈 슬롯 처리, 비언어 확인 등 핵심 기능 일부가 아직 완성되지 않았다.

---

## 3. 현재 상태 전이

현재 `decision_node.py`에서 실질적으로 사용하는 상태는 다음과 같다.

| 상태 | 의미 |
|---|---|
| `IDLE` | 사람 감지 대기 |
| `ORDER_LISTEN` | 주문 또는 재주문 입력 대기 |
| `ORDER_CONFIRM` | 주문 내용 확인 응답 대기 |
| `ORDER_COMPLETE` | 주문 확정 완료 |

현재 주요 상태 전이는 다음과 같다.

| 현재 상태 | 입력 또는 사건 | 다음 상태 | 현재 동작 |
|---|---|---|---|
| `IDLE` | 얼굴이 `False → True` | `ORDER_LISTEN` | 인사 후 STT 시작 |
| `ORDER_LISTEN` | 높은 신뢰도의 `ORDER` | `ORDER_CONFIRM` | 주문 확인 질문 |
| `ORDER_LISTEN` | 낮은 신뢰도 | 상태 유지 | 재질문 TTS만 출력 |
| `ORDER_LISTEN` | `CANCEL` | `IDLE` | 주문 초기화 |
| `ORDER_LISTEN` | 사람 사라짐 | `IDLE` | 주문 초기화 |
| `ORDER_CONFIRM` | 긍정 응답 | `ORDER_COMPLETE` | 주문 확정 |
| `ORDER_CONFIRM` | 부정 응답 | `ORDER_LISTEN` | 주문 삭제 후 재주문 요청 |
| `ORDER_CONFIRM` | 사람 사라짐 | `ORDER_CONFIRM` 유지 | 확인 응답 계속 대기 |
| `ORDER_COMPLETE` | 사람 사라짐 | 변화 없음 | 상태가 초기화되지 않음 |
| `ORDER_COMPLETE` | 새 사람 감지 | 변화 없음 | `IDLE`이 아니므로 무시될 수 있음 |

---

# 4. 현재 문제점과 수정 방향

## 문제 1. 주문 확정 후 `IDLE` 상태로 복귀하지 않음

### 현재 상태

사용자가 주문 확인 질문에 긍정하면 다음과 같이 처리된다.

```text
ORDER_CONFIRM → ORDER_COMPLETE
```

하지만 이후 `ORDER_COMPLETE → IDLE` 전이가 구현되어 있지 않다.

### 영향

- 첫 주문은 정상적으로 끝나더라도 다음 손님의 주문이 시작되지 않을 수 있다.
- 새 사람이 감지되어도 현재 상태가 `IDLE`이 아니므로 감지 이벤트가 무시될 수 있다.
- 장시간 실행 시 시스템이 `ORDER_COMPLETE`에 고정될 가능성이 있다.
- 관리자 페이지의 상태도 실제 매장 흐름과 맞지 않게 유지될 수 있다.

### 수정 방향

주문 확정 후 다음 두 단계로 나누는 것이 적절하다.

```text
ORDER_CONFIRM
    ↓ 긍정
ORDER_COMPLETE
    ↓ 완료 안내 및 저장 종료 후
IDLE
```

`ORDER_COMPLETE`는 주문 저장, 완료 TTS, 화면 표시 등 종료 처리를 위한 짧은 상태로 사용한다.

### 권장 구현

다음 중 한 가지 방식을 선택한다.

#### 방법 A. 완료 응답 직후 타이머로 초기화

- `ORDER_CONFIRMED` 발행
- 완료 TTS가 끝날 시간을 고려해 약 2~4초 후 `IDLE` 복귀
- `current_order = None`
- 사람 감지 플래그를 재설정할지 정책 결정

#### 방법 B. TTS 완료 이벤트를 받은 뒤 초기화

- TTS 노드가 `/tts/status = done` 발행
- `decision_node`가 완료 상태에서 이를 받아 `IDLE` 복귀
- 실제 음성 출력 종료 시점과 상태 전이가 일치하므로 장기적으로 더 안정적

### 권장안

중간 시연 전에는 방법 A로 빠르게 구현하고, 이후 방법 B로 개선한다.

### 완료 기준

- 주문 확정 안내 후 자동으로 `IDLE`이 된다.
- 다음 사람이 접근하면 새 주문이 정상 시작된다.
- 이전 주문 내용이 새 주문에 남지 않는다.

---

## 문제 2. 낮은 NLU 신뢰도 재질문 후 마이크가 자동으로 다시 켜지지 않음

### 현재 상태

NLU 결과가 다음 조건에 해당하면 `REPROMPT`가 발생한다.

```text
confidence < 0.75
또는
needs_reprompt = True
```

로봇은 다음 문장을 출력한다.

```text
죄송해요. 다시 한 번 말씀해주시겠어요?
```

그러나 `action_node.py`는 다음 결정에서만 STT를 다시 실행한다.

- `START_ORDER`
- `CONFIRM_ORDER`
- `REORDER_REQUEST`

`REPROMPT`는 STT 재실행 조건에 포함되어 있지 않다.

### 영향

- 재질문은 하지만 실제로 다음 음성을 받지 않는다.
- 사용자는 다시 말해도 시스템이 듣지 않는다고 느낄 수 있다.
- 낮은 신뢰도 상황에서 대화가 사실상 중단된다.

### 수정 방향

`action_node.py`에서 `REPROMPT`도 STT 재실행 대상으로 추가한다.

```text
REPROMPT
    ↓ 재질문 TTS
2.5~4초 후
/stt/trigger = start
```

### 추가로 필요한 처리

- NLU 재질문 횟수를 별도로 관리한다.
- 같은 단계에서 일정 횟수 이상 실패하면 화면 입력 또는 수동 선택으로 전환한다.
- STT 실패 횟수와 NLU 저신뢰도 횟수를 구분해 관리하는 것이 좋다.

예시:

```text
stt_retry_count
nlu_reprompt_count
slot_retry_count
```

### 권장 정책

- NLU 저신뢰도 1~2회: 동일 질문 재시도
- 3회 이상: 화면 직접 선택 안내 또는 초기화

### 완료 기준

- 낮은 신뢰도 응답 후 안내 음성이 끝나면 자동으로 다시 녹음한다.
- 최대 재질문 횟수를 넘으면 무한 반복하지 않는다.

---

## 문제 3. 메뉴·수량·온도 누락 여부를 검사하지 않고 바로 주문 확인으로 이동함

### 현재 상태

현재 `ORDER` 의도로 판단되면 다음 세 값을 저장한 뒤 바로 `ORDER_CONFIRM`으로 이동한다.

```text
menu
temperature
quantity
```

하지만 값이 `None`인지 검사하지 않는다.

### 영향

- 사용자가 일부 정보만 말해도 완전한 주문처럼 확인 질문을 한다.
- 주문 데이터에 `None`이 포함될 수 있다.
- 사용자가 말하지 않은 정보를 시스템이 임의로 추정할 수 있다.
- 설계 문서의 `FILLING_SLOT` 흐름과 실제 코드가 일치하지 않는다.

### 수정 방향

주문 의도가 들어오면 먼저 필수 슬롯을 검사해야 한다.

권장 순서:

```text
1. menu
2. quantity
3. temperature
```

단, 온도 선택이 필요하지 않은 메뉴는 메뉴 정책에 따라 자동 보완한다.

### 권장 상태 추가

```text
ORDER_LISTEN
    ↓ NLU 분석
FILLING_SLOT
    ↓ 모든 필수 슬롯 완료
ORDER_CONFIRM
```

### 필요한 데이터 구조

```json
{
  "menu": "아메리카노",
  "quantity": null,
  "temperature": null,
  "missing_slots": ["quantity", "temperature"],
  "waiting_for": "quantity"
}
```

### 질문 예시

```text
menu 누락:
어떤 메뉴를 주문하시겠어요?

quantity 누락:
아메리카노 몇 잔 주문하시겠어요?

temperature 누락:
아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?
```

### 완료 기준

- 필수 슬롯이 하나라도 비어 있으면 최종 확인으로 가지 않는다.
- 한 번에 여러 슬롯을 보완한 응답도 반영할 수 있다.
- 모든 필수 슬롯이 채워진 경우에만 `ORDER_CONFIRM`으로 이동한다.

---

## 문제 4. 수량이 없을 때 임의로 1잔으로 확인함

### 현재 상태

확인 문장을 생성할 때 `quantity`가 없으면 다음과 같이 한 잔으로 처리한다.

```text
quantity가 존재하면: N잔
quantity가 없으면: 한 잔
```

### 영향

- 사용자가 수량을 말하지 않았는데 시스템이 임의로 주문 수량을 결정한다.
- 주문 오류와 결제 오류로 이어질 수 있다.
- `docs/order_dialogue_rules.md`의 정책과 충돌한다.

### 수정 방향

- `quantity=None`이면 확인 문장을 만들지 않는다.
- `FILLING_SLOT`으로 이동해 수량을 반드시 질문한다.
- 화면 표시에서도 `None`을 1잔으로 치환하지 않는다.

### 완료 기준

다음 입력에 대해 바로 “한 잔 맞으신가요?”라고 묻지 않아야 한다.

```text
아메리카노 주세요
```

대신 다음과 같이 질문해야 한다.

```text
아메리카노 몇 잔 주문하시겠어요?
```

---

## 문제 5. 슬롯별 신뢰도 평가가 구현되어 있지 않음

### 현재 상태

현재 의사결정은 단일 통합 `confidence` 값만 사용한다.

```text
confidence >= 0.75 → 정상 처리
confidence < 0.75 → 전체 문장 재질문
```

설계 문서에는 슬롯별 신뢰도 기준이 존재하지만 실제 `decision_node.py`에는 반영되어 있지 않다.

### 영향

- 메뉴만 불확실해도 전체 주문을 다시 말하게 한다.
- 수량이나 온도만 낮은 경우에도 해당 슬롯만 재질문하지 못한다.
- 사용자 대화가 불필요하게 길어진다.
- NLU 모델의 멀티태스크 출력 정보를 충분히 활용하지 못한다.

### 수정 방향

NLU 결과에 다음 정보를 명확히 포함한다.

```json
{
  "intent_confidence": 0.91,
  "slot_confidence": {
    "menu": 0.88,
    "quantity": 0.52,
    "temperature": 0.84
  }
}
```

의사결정 규칙 예시:

```text
intent 신뢰도 낮음 → 전체 문장 재질문
menu 신뢰도 낮음 → 메뉴 재질문
quantity 신뢰도 낮음 → 수량 재질문
temperature 신뢰도 낮음 → 온도 재질문
```

### 초기 기준안

설계 문서 기준을 시작점으로 사용한다.

| 항목 | 초기 임계값 |
|---|---:|
| intent | 0.60 |
| menu | 0.60 |
| quantity | 0.55 |
| temperature | 0.55 |

최종 임계값은 검증 데이터와 실제 음성 환경 테스트를 통해 조정한다.

### 완료 기준

- 낮은 신뢰도의 슬롯만 선택적으로 다시 질문한다.
- 모든 슬롯 신뢰도가 충분할 때만 최종 확인한다.

---

## 문제 6. 설계 문서와 실제 상태 이름이 일치하지 않음

### 현재 상태

설계 문서는 다음 상태를 정의한다.

```text
IDLE
ANALYZING
FILLING_SLOT
CONFIRMING
MODIFYING
COMPLETED
CANCELLED
ERROR
```

실제 코드는 다음 상태를 중심으로 사용한다.

```text
IDLE
ORDER_LISTEN
ORDER_CONFIRM
ORDER_COMPLETE
```

### 영향

- 팀원마다 상태 이름을 다르게 사용할 수 있다.
- 웹 관리자 페이지, ROS 노드, 보고서의 상태가 서로 달라질 수 있다.
- 기능 추가 시 조건문 누락과 상태 전이 버그가 발생하기 쉽다.

### 수정 방향

상태 이름을 하나의 공통 정의로 통합한다.

권장 방법:

```python
from enum import Enum

class DialogueState(str, Enum):
    IDLE = "IDLE"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    ANALYZING = "ANALYZING"
    FILLING_SLOT = "FILLING_SLOT"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
```

### 권장 최종 상태 흐름

```text
IDLE
  ↓ 사람 감지
GREETING
  ↓ 인사 완료
LISTENING
  ↓ 음성 입력 완료
ANALYZING
  ├─ 누락 또는 낮은 슬롯 신뢰도 → FILLING_SLOT
  ├─ 주문 완성 → CONFIRMING
  └─ 오류 → ERROR
FILLING_SLOT
  ├─ 추가 슬롯 필요 → FILLING_SLOT
  └─ 주문 완성 → CONFIRMING
CONFIRMING
  ├─ 긍정 → COMPLETED
  ├─ 부정 → LISTENING 또는 FILLING_SLOT
  └─ 취소 → CANCELLED
COMPLETED
  ↓ 종료 처리
IDLE
CANCELLED
  ↓ 취소 안내
IDLE
```

### 완료 기준

- 문서, ROS 메시지, 관리자 페이지에서 같은 상태명을 사용한다.
- 상태 문자열을 여러 파일에 직접 작성하지 않고 공통 상수 또는 Enum으로 관리한다.

---

## 문제 7. 끄덕임과 좌우 흔들기가 주문 확인에 연결되어 있지 않음

### 현재 상태

`vision_node.py`에는 `/head_gesture` publisher가 존재하지만 시작 시 `NONE`을 발행하는 것 외에 실제 제스처 분석이 없다.

`decision_node.py`도 `/head_gesture`를 구독하지 않는다.

### 영향

- 사용자가 끄덕이거나 고개를 좌우로 흔들어도 주문 상태가 변하지 않는다.
- 비언어 인식을 활용한다는 프로젝트 핵심 기능이 시연되지 않는다.
- 음성 확인만 가능하여 Physical AI 요소가 약해진다.

### 수정 방향

비전 노드에서 일정 프레임 동안 얼굴 중심점 또는 머리 자세 변화를 추적한다.

출력 예시:

```text
/head_gesture = NOD
/head_gesture = SHAKE
/head_gesture = NONE
```

의사결정 노드는 `CONFIRMING` 상태에서만 해당 값을 사용한다.

```text
CONFIRMING + NOD → 긍정 처리
CONFIRMING + SHAKE → 부정 처리
그 외 상태의 제스처 → 무시
```

### 충돌 방지 규칙

음성과 제스처가 동시에 들어올 수 있으므로 다음 정책을 정해야 한다.

권장안:

1. 먼저 들어온 유효 응답을 사용한다.
2. 한 응답이 처리된 후 일정 시간 동안 추가 응답을 무시한다.
3. 음성과 제스처가 짧은 시간 내 서로 충돌하면 재확인한다.

예시:

```text
음성: 네
제스처: SHAKE
→ 입력이 충돌했습니다. 주문 내용이 맞는지 다시 확인해주세요.
```

### 완료 기준

- 확인 상태에서 끄덕임으로 주문이 확정된다.
- 좌우 흔들기로 재주문 단계로 이동한다.
- 한 동작이 여러 번 중복 처리되지 않는다.

---

## 문제 8. 현재 사람 감지는 사람 객체가 아니라 정면 얼굴 감지에 가까움

### 현재 상태

OpenCV Haar Cascade로 정면 얼굴을 검출한다.

### 영향

- 옆모습이나 마스크 착용 상태에서 감지가 불안정할 수 있다.
- 얼굴이 화면 밖에 있고 몸만 보이면 사람으로 판단하지 못한다.
- 조명과 카메라 각도에 영향을 크게 받을 수 있다.

### 수정 방향

단계적으로 개선한다.

#### 1단계

현재 Haar Cascade를 유지하면서 실제 카메라 환경에서 다음 값을 조정한다.

- `min_face_width`
- `min_face_height`
- `minNeighbors`
- 연속 검출 프레임 수
- 연속 미검출 프레임 수

#### 2단계

사람 객체 검출 모델 또는 얼굴 랜드마크 기반 감지로 교체한다.

가능한 후보:

- MediaPipe Face Detection
- MediaPipe Face Mesh
- YOLO person detection

#### 권장안

끄덕임과 좌우 흔들기까지 구현해야 하므로 MediaPipe Face Mesh 또는 머리 자세 추정 방식이 전체 시스템 연결 측면에서 적합하다.

### 완료 기준

- 카메라 앞 실제 주문 위치에서 안정적으로 사람 접근을 감지한다.
- 짧은 오검출로 주문이 반복 시작되지 않는다.
- 얼굴을 잠시 돌려도 즉시 주문이 취소되지 않는다.

---

## 문제 9. 프로그램 시작 시 이미 사람이 있으면 주문이 시작되지 않을 수 있음

### 현재 상태

첫 번째 `/human_presence` 메시지는 초기값 저장에만 사용하고 주문 시작 이벤트로 처리하지 않는다.

따라서 프로그램 실행 전에 이미 사람이 카메라 앞에 있으면 첫 메시지가 `True`여도 인사가 시작되지 않을 수 있다.

### 영향

- 시연 시작 시 사람이 이미 카메라 앞에 있으면 시스템이 반응하지 않을 수 있다.
- 사용자가 카메라 앞에서 벗어났다가 다시 들어와야 시작되는 현상이 생길 수 있다.

### 수정 방향

초기값이 `True`이고 현재 상태가 `IDLE`이면 바로 `handle_human_detected()`를 호출하도록 수정한다.

단, 노드 실행 직후 카메라 오검출로 인사가 시작되지 않도록 안정화 시간을 둘 수 있다.

권장 정책:

```text
노드 실행
→ 1~2초 안정화
→ 연속 얼굴 검출 조건 충족
→ 초기값이 True여도 주문 시작
```

### 완료 기준

- 프로그램 실행 시 이미 사람이 앞에 있어도 정상적으로 주문을 시작한다.
- 초기 카메라 노이즈로 잘못 시작되지 않는다.

---

## 문제 10. 확인 질문과 녹음 시작 사이의 고정 지연 시간이 길고 불안정함

### 현재 상태

- 시작 인사 후 3초 뒤 STT 시작
- 주문 확인 질문 후 4초 뒤 STT 시작
- STT는 시작 후 4초 동안 고정 녹음

### 영향

- TTS 길이가 짧으면 사용자가 오래 기다려야 한다.
- TTS 길이가 길면 로봇 음성이 녹음에 들어갈 수 있다.
- 사용자가 질문 도중 대답하면 응답을 놓친다.
- 전체 주문 시간이 길어진다.

### 수정 방향

장기적으로 고정 `sleep` 대신 TTS 상태 이벤트를 사용한다.

```text
TTS speaking
→ /tts/status = done
→ STT trigger
```

추가 개선안:

- 고정 4초 녹음 대신 VAD 기반 발화 종료 감지
- 최대 녹음 시간만 제한
- 사용자의 음성이 시작되면 녹음 유지
- 일정 무음 구간 후 자동 종료

### 완료 기준

- 로봇 TTS가 녹음 파일에 들어가지 않는다.
- 사용자가 자연스러운 시점에 답할 수 있다.
- 불필요한 고정 대기 시간이 줄어든다.

---

## 문제 11. 주문 완료 데이터 저장과 관리자 페이지 반영 시점이 명확하지 않음

### 현재 상태

`ORDER_CONFIRMED` 메시지에 확정 주문이 포함되지만, 주문 완료 데이터를 어디에서 영구 저장할지 역할이 명확히 분리되어 있지 않다.

### 영향

- 주문 확정은 되었지만 관리자 페이지에 누락될 수 있다.
- ROS 메시지가 사라지면 주문 기록이 남지 않을 수 있다.
- 상태 표시와 실제 주문 저장 결과가 달라질 수 있다.

### 수정 방향

주문 확정 처리의 책임을 명확히 정한다.

권장 구조:

```text
decision_node
→ ORDER_CONFIRMED 생성

order_service 또는 API
→ DB 저장
→ order_id 생성
→ 저장 성공 응답

decision_node/action_node
→ 저장 성공 후 완료 안내
```

최소 구현에서는 `api/ros_bridge.py` 또는 별도 order logger가 `ORDER_CONFIRMED`를 받아 SQLite에 저장하도록 할 수 있다.

저장할 기본 항목:

```text
order_id
session_id
created_at
menu
quantity
temperature
intent_confidence
slot_confidence
stt_text
final_status
```

### 완료 기준

- 주문 확정마다 한 건의 기록만 저장된다.
- 중복 메시지로 동일 주문이 여러 번 저장되지 않는다.
- 관리자 페이지에서 확정 주문을 확인할 수 있다.

---

# 5. 우선순위별 작업 계획

## P0. 반드시 먼저 수정해야 하는 항목

중간 시연과 기본 주문 성공을 위해 가장 먼저 처리해야 한다.

### P0-1. 주문 완료 후 `IDLE` 복귀

- [ ] `ORDER_COMPLETE → IDLE` 전이 추가
- [ ] 이전 주문 데이터 초기화
- [ ] 다음 사람 접근 시 새 주문 시작 확인

### P0-2. `REPROMPT` 후 STT 자동 재시작

- [ ] `action_node.py`에 `REPROMPT` 처리 추가
- [ ] NLU 재질문 횟수 제한 추가
- [ ] 최대 횟수 초과 시 화면 안내 또는 초기화

### P0-3. 빈 슬롯 검사

- [ ] `menu`, `quantity`, `temperature` 누락 검사
- [ ] `FILLING_SLOT` 또는 동등한 상태 구현
- [ ] `waiting_for` 저장
- [ ] 슬롯별 질문 생성

### P0-4. 수량 기본값 1 제거

- [ ] `make_order_confirm_speech()`에서 임의 1잔 처리 제거
- [ ] `action_node.py` 화면 표시에서도 임의 1잔 처리 제거

### P0-5. 기본 상태 전이 테스트

- [ ] 완전 주문
- [ ] 수량 누락
- [ ] 온도 누락
- [ ] 낮은 신뢰도
- [ ] 긍정 확인
- [ ] 부정 확인
- [ ] 주문 완료 후 다음 주문

---

## P1. 다음 단계에서 구현해야 하는 항목

### P1-1. 상태 이름 통합

- [ ] 공통 `DialogueState` 정의
- [ ] 문서, ROS, 웹 상태명 통합
- [ ] 상태 전이 로그 통일

### P1-2. 슬롯별 confidence 적용

- [ ] NLU 결과 스키마 확정
- [ ] 슬롯별 confidence 전달
- [ ] 낮은 슬롯만 재질문
- [ ] 검증 데이터 기반 임계값 조정

### P1-3. 주문 저장 연결

- [ ] 확정 주문 저장 위치 결정
- [ ] SQLite 또는 API 연동
- [ ] 관리자 페이지 주문 현황 반영
- [ ] 중복 저장 방지

### P1-4. 시작 시 사람 존재 처리

- [ ] 초기 `True` 입력 처리
- [ ] 카메라 안정화 시간 적용

### P1-5. TTS와 STT 동기화

- [ ] `/tts/status` 정의
- [ ] TTS 완료 후 STT 시작
- [ ] 고정 지연 최소화

---

## P2. 기능 완성도를 높이기 위한 항목

### P2-1. 끄덕임·좌우 흔들기 구현

- [ ] 얼굴 랜드마크 또는 머리 자세 추정
- [ ] `/head_gesture`에 `NOD`, `SHAKE`, `NONE` 발행
- [ ] 확인 상태에만 적용
- [ ] 음성 입력과 충돌 처리

### P2-2. 사람 감지 개선

- [ ] 실제 환경에서 Haar 파라미터 튜닝
- [ ] MediaPipe 또는 YOLO 방식 비교
- [ ] 조명, 거리, 마스크 환경 테스트

### P2-3. 복합 주문

- [ ] `items` 배열 구조 적용
- [ ] 여러 메뉴 분리
- [ ] 항목별 누락 슬롯 처리
- [ ] 전체 주문 최종 확인

### P2-4. 수정 및 부분 취소

- [ ] 메뉴·수량·온도 개별 수정
- [ ] 전체 취소
- [ ] 특정 메뉴만 취소

---

# 6. 권장 최종 주문 흐름

```text
[IDLE]
사람 감지 대기
    ↓
[GREETING]
인사 TTS 및 화면 표시
    ↓ TTS 완료
[LISTENING]
사용자 음성 수집
    ↓
[ANALYZING]
STT 및 NLU 분석
    ├─ STT 실패 → LISTENING 재시도
    ├─ intent 신뢰도 낮음 → LISTENING 재시도
    ├─ 필수 슬롯 누락 또는 낮은 슬롯 신뢰도 → FILLING_SLOT
    ├─ 완전한 주문 → CONFIRMING
    ├─ 취소 → CANCELLED
    └─ 오류 → ERROR

[FILLING_SLOT]
현재 waiting_for 슬롯 질문
    ↓ 사용자 응답
[ANALYZING]
    ├─ 추가 슬롯 필요 → FILLING_SLOT
    └─ 주문 완성 → CONFIRMING

[CONFIRMING]
주문 내용 최종 확인
    ├─ 음성 긍정 또는 끄덕임 → COMPLETED
    ├─ 음성 부정 또는 좌우 흔들기 → LISTENING 또는 MODIFYING
    ├─ 취소 → CANCELLED
    └─ 응답 불명확 → CONFIRMING 재질문

[COMPLETED]
주문 DB 저장 및 완료 안내
    ↓
[IDLE]

[CANCELLED]
취소 안내 및 주문 데이터 초기화
    ↓
[IDLE]

[ERROR]
복구 안내 또는 화면 입력 유도
    ↓
[IDLE 또는 LISTENING]
```

---

# 7. 테스트 시나리오

## 테스트 1. 완전한 단일 주문

```text
사용자: 아이스 아메리카노 두 잔 주세요.
로봇: 아이스 아메리카노 2잔 맞으신가요?
사용자: 네.
로봇: 주문이 확정되었습니다.
```

확인 항목:

- [ ] `IDLE → LISTENING → ANALYZING → CONFIRMING → COMPLETED → IDLE`
- [ ] 주문 데이터가 정확히 저장됨
- [ ] 다음 주문을 받을 수 있음

## 테스트 2. 수량 누락

```text
사용자: 아메리카노 주세요.
로봇: 아메리카노 몇 잔 주문하시겠어요?
사용자: 한 잔이요.
로봇: 아이스로 드릴까요, 따뜻하게 드릴까요?
사용자: 아이스로요.
로봇: 아이스 아메리카노 1잔 맞으신가요?
```

확인 항목:

- [ ] 수량을 임의로 1잔 처리하지 않음
- [ ] `waiting_for=quantity`가 정상 설정됨
- [ ] 다음 누락 슬롯으로 이동함

## 테스트 3. 온도 누락

```text
사용자: 아메리카노 한 잔 주세요.
로봇: 아이스로 드릴까요, 따뜻하게 드릴까요?
```

확인 항목:

- [ ] 온도만 재질문함
- [ ] 기존 메뉴와 수량이 유지됨

## 테스트 4. 낮은 신뢰도

```text
사용자 발화가 불명확함
로봇: 다시 한 번 말씀해주시겠어요?
사용자: 아이스 아메리카노 한 잔 주세요.
```

확인 항목:

- [ ] 재질문 후 마이크가 자동으로 다시 켜짐
- [ ] 무한 반복하지 않음

## 테스트 5. 부정 응답

```text
로봇: 아이스 아메리카노 1잔 맞으신가요?
사용자: 아니요.
로봇: 알겠습니다. 다시 주문해 주세요.
```

확인 항목:

- [ ] 이전 주문 삭제
- [ ] 재주문 녹음 자동 시작

## 테스트 6. 주문 완료 후 다음 손님

```text
첫 번째 주문 완료
→ 사람 퇴장
→ 다음 사람 접근
```

확인 항목:

- [ ] 상태가 `IDLE`로 돌아감
- [ ] 두 번째 주문이 정상 시작됨
- [ ] 첫 주문 정보가 섞이지 않음

## 테스트 7. 비언어 확인

```text
로봇: 주문 내용이 맞으신가요?
사용자: 끄덕임
```

확인 항목:

- [ ] `NOD`가 한 번만 처리됨
- [ ] 주문 확정
- [ ] 음성 응답과 중복 처리되지 않음

---

# 8. 구현 시 파일별 작업 예상

## `vision_node.py`

- 사람 감지 초기값 처리 개선
- 끄덕임·좌우 흔들기 인식 추가
- `/head_gesture` 실제 발행
- 감지 안정화 및 중복 이벤트 방지

## `stt_node.py`

- 현재 고정 4초 녹음 유지 또는 VAD 종료 방식 검토
- TTS 종료 후 트리거되는 구조와 연결
- 상태 및 오류 코드 명확화

## `nlu_node.py`

- 슬롯별 confidence를 포함한 결과 발행
- NLU 결과 스키마 검증

## `model_wrapper.py`

- 모델별 출력을 공통 스키마로 정규화
- `intent_confidence`, `slot_confidence`, `items` 지원
- 누락 슬롯 계산에 필요한 원본 출력 유지

## `decision_node.py`

- 공통 상태 Enum 적용
- 빈 슬롯 검사 및 `waiting_for` 관리
- 슬롯별 재질문
- 주문 완료 후 초기화
- `/head_gesture` 구독
- 재질문 횟수 및 오류 복구

## `action_node.py`

- `REPROMPT` 후 STT 재실행
- `FILLING_SLOT` 질문 후 STT 재실행
- 고정 시간 대신 TTS 완료 이벤트 기반 트리거
- 화면 표시에서 임의 기본값 제거

## `api/ros_bridge.py`

- 상태명 통합
- 확정 주문 수신 및 관리자 페이지 반영
- 주문 저장 결과와 응답 상태 연결

---

# 9. 팀 작업 권장 분담

아래는 기능 충돌을 줄이기 위한 예시 분담이다.

| 작업 영역 | 주요 파일 | 작업 내용 |
|---|---|---|
| 상태 및 대화 관리 | `decision_node.py` | 상태 전이, 빈 슬롯, 확인, 초기화 |
| 음성 파이프라인 | `stt_node.py`, `action_node.py` | 재녹음, TTS-STT 동기화, 실패 처리 |
| NLU 출력 정리 | `nlu_node.py`, `model_wrapper.py` | confidence 스키마, 누락 슬롯 정보 |
| 비전 입력 | `vision_node.py` | 사람 감지, 끄덕임, 좌우 흔들기 |
| 웹 및 저장 | `api/ros_bridge.py`, DB 관련 코드 | 주문 기록, 관리자 페이지 반영 |

작업 전 공통으로 확정해야 할 항목:

1. 최종 상태 이름
2. NLU 결과 JSON 스키마
3. 주문 데이터 JSON 스키마
4. 재질문 최대 횟수
5. 주문 완료 후 `IDLE` 복귀 시점
6. 음성과 제스처 충돌 처리 정책

---

# 10. 가장 먼저 할 일

현재 단계에서는 아래 순서로 진행하는 것이 가장 안전하다.

```text
1. 상태 이름과 주문 JSON 스키마 확정
2. 주문 완료 후 IDLE 복귀 수정
3. REPROMPT 후 STT 자동 재실행 수정
4. 수량 기본값 1 제거
5. 빈 슬롯 및 waiting_for 구현
6. 단일 주문 전체 테스트
7. 주문 저장과 관리자 페이지 연결
8. 슬롯별 confidence 적용
9. 끄덕임·좌우 흔들기 연결
10. 복합 주문 및 수정 기능 확장
```

중간 시연 기준 최소 성공 조건은 다음과 같다.

```text
사람 감지
→ 인사
→ 음성 주문
→ STT
→ NLU
→ 누락 슬롯 질문
→ 최종 확인
→ 네/아니요 처리
→ 주문 저장
→ IDLE 복귀
→ 다음 주문 가능
```

---

## 11. 요약

현재 시스템은 얼굴 감지부터 STT, NLU, 주문 확인까지의 큰 흐름은 연결되어 있다. 그러나 실제 매장에서 연속으로 주문을 받으려면 다음 네 항목을 우선 수정해야 한다.

1. 주문 확정 후 `IDLE` 복귀
2. `REPROMPT` 후 자동 재녹음
3. 빈 슬롯 보완 상태 구현
4. 누락 수량을 임의로 1잔 처리하는 로직 제거

그 다음 상태명 통합, 슬롯별 신뢰도, 주문 저장, 비언어 확인을 순서대로 연결해야 한다.
