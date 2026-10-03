# Response Manager

Pumpkin 주문 대화의 사용자 응답 문장을 Decision 및 Action 로직에서 분리합니다.

## 책임 분리

```text
NLU
→ /intent_result
→ Decision Node
   - FSM 상태 전환
   - 주문 병합 및 누락 슬롯 선택
   - response_key와 response_args 생성
→ /decision_result
→ Response Manager Node
   - speech와 display_text 생성
→ /response_result
→ Action Node
   - 표정·화면·고개·팔 동작 결정
   - TTS 완료 후 STT 시작
→ /robot_action
```

### Decision Node

Decision Node는 완성된 한국어 문장을 발행하지 않습니다.

```json
{
  "decision": "ASK_TEMPERATURE",
  "response_key": "ask_temperature",
  "response_args": {
    "item_id": 0,
    "slot": "temperature",
    "menu": "아메리카노"
  },
  "reason": "missing_temperature",
  "waiting_for": {
    "item_id": 0,
    "slot": "temperature"
  }
}
```

### Response Manager

`response_manager.py`는 ROS에 의존하지 않는 결정적 템플릿 렌더러입니다. `response_manager_node.py`는 `/decision_result`와 `/response_request`를 구독하여 `/response_result`를 발행합니다.

```json
{
  "decision": "ASK_TEMPERATURE",
  "response_key": "ask_temperature",
  "speech": "아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?",
  "display_text": "아메리카노 온도를 선택해 주세요"
}
```

### Action Node

Action Node는 `/response_result`만 구독합니다. 일반 응답 문장을 만들지 않고, 받은 `speech`와 `display_text`를 TTS·LCD·표정·몸짓 명령으로 변환합니다.

STT 재시도 문장도 Action Node 내부에서 생성하지 않습니다. Action Node는 `/response_request`에 `stt_retry` 또는 `stt_failed`를 발행하고 Response Manager가 실제 문장을 생성합니다.

시스템 오류에 사용하는 최후의 비상 문장만 Action Node에 남아 있습니다.

## Topic

| Topic | 발행 → 구독 | 역할 |
|---|---|---|
| `/decision_result` | Decision → Response Manager | 구조화된 판단 결과 |
| `/response_request` | Action → Response Manager | STT 재시도 같은 실행 단계 응답 요청 |
| `/response_result` | Response Manager → Action/Web | `speech`, `display_text`가 포함된 응답 |
| `/robot_action` | Action → TTS/Web/Hardware | 최종 추상 행동 |

## 주요 response_key

```text
start_order
ask_menu
ask_quantity
ask_temperature
confirm_order
order_confirmed
modify_order
ask_correction_target
cancel_order
no_active_order
restart_order
nlu_reprompt
nlu_retry_exhausted
slot_retry_exhausted
out_of_policy
stt_retry
stt_failed
guide_customer
payment_guide
```

## 터미널 챗봇 테스트

웹사이트 없이 같은 터미널에서 문장을 입력하고 로봇 응답을 이어서 확인할 수 있습니다.

먼저 터미널 1에서 ROS 파이프라인을 실행합니다.

```bash
cd ~/pumpkin
PUMPKIN_NLU_DEVICE=cuda bash scripts/run_ros_voice_nodes.sh
```

터미널 2에서 ROS 환경을 적용하고 채팅 프로그램을 실행합니다.

```bash
cd ~/pumpkin
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/terminal_chat.py
```

실행 예시:

```text
Pumpkin 터미널 대화 테스트
명령어: /help, /state, /debug, /clear, /quit

나 > 아메리카노 하나요
로봇 > 아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?

나 > 따뜻하게요
로봇 > 따뜻한 아메리카노 1잔 맞으신가요?

나 > 네
로봇 > 주문이 확정되었습니다. 감사합니다.
```

지원 명령:

| 명령 | 기능 |
|---|---|
| `/help` | 사용 가능한 명령 표시 |
| `/state` | 마지막 Decision, Response, Action JSON 표시 |
| `/debug` | 전체 JSON 실시간 출력 켜기·끄기 |
| `/clear` | 터미널 클라이언트에 저장된 마지막 결과 초기화 |
| `/quit` | 프로그램 종료 |

응답 대기 시간을 바꾸거나 전체 JSON을 처음부터 표시할 수도 있습니다.

```bash
python3 scripts/terminal_chat.py --timeout 30 --debug
```

이 프로그램은 ROS 노드를 직접 실행하지 않습니다. `/voice_text` 구독자가 없으면 먼저 `run_ros_voice_nodes.sh`를 실행하라는 오류를 표시합니다.

## 자동 테스트

```bash
cd ~/pumpkin/ros2_ws

PYTHONPATH=src/robot_controller \
python3 -m pytest \
  src/robot_controller/test/test_dialogue_flow.py \
  src/robot_controller/test/test_dialogue_pipeline_scenarios.py \
  src/robot_controller/test/test_response_manager.py \
  -q
```

핵심 확인 항목:

- `/decision_result`에 `speech`가 없음
- `/response_result`에 `speech`와 `display_text`가 있음
- 주문 확인 문장에 모든 주문 항목이 포함됨
- 항목별 질문에 `waiting_for.item_id`의 메뉴가 포함됨
- Response Manager가 Decision Node의 FSM 상태를 변경하지 않음
- `/response_result` 이후에만 `/robot_action`이 생성됨
- TTS `speaking → done` 이후에만 STT가 시작됨
- 주문 완료 TTS 이후 Decision Node가 `IDLE`로 복귀함
