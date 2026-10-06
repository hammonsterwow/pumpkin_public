# Response Manager

Pumpkin 주문 대화의 사용자 응답 문장을 Decision/FSM과 Action/하드웨어 로직에서 분리하는 계층입니다.

## 책임 분리

```text
NLU
→ /intent_result
→ Decision Node
   - FSM 상태
   - 주문 병합/검증
   - response_key + response_args
→ /decision_result
→ Response Manager Node
   - speech + display_text
→ /response_result
→ Action Node
   - 표정·고개·팔
   - TTS 실행
   - 다음 STT turn 제어
→ /robot_action
```

Decision Node는 대화 판단과 구조화된 응답 요청을 만들고, Response Manager가 실제 한국어 문장을 렌더링합니다. Action Node는 응답 문장을 다시 작성하지 않고 받은 결과에 물리 행동을 결합합니다.

## 예시

Decision:

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

Response:

```json
{
  "decision": "ASK_TEMPERATURE",
  "response_key": "ask_temperature",
  "speech": "아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?",
  "display_text": "아메리카노 온도를 선택해 주세요"
}
```

## 구현 파일

- `robot_controller/response_manager.py`: ROS에 의존하지 않는 템플릿 렌더러
- `robot_controller/response_manager_node.py`: ROS Topic 입출력
- `robot_controller/response_payload_builder.py`: 응답 payload 구성 보조
- `robot_controller/action_node.py`: Response 결과를 로봇 행동으로 변환

## Topic

| Topic | 흐름 | 역할 |
|---|---|---|
| `/decision_result` | Decision → Response Manager | 구조화된 판단 |
| `/response_request` | Action → Response Manager | STT 재질문 등 실행 단계 응답 요청 |
| `/response_result` | Response Manager → Action/Web | `speech`, `display_text` |
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
preorder_pickup_ready
```

## STT 재질문

회복 가능한 STT 실패는 Action Node가 `/response_request`에 `stt_retry`를 요청하고 Response Manager가 재질문 문장을 생성합니다. 오디오 장치나 STT runtime 자체의 오류는 `stt_failed` 응답으로 전환하고 자동 재시도를 중단합니다.

## 실행 확인

전체 파이프라인:

```bash
cd ~/pumpkin_public
bash scripts/run_robot_interaction_demo.sh
```

Topic 확인:

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin_public/ros2_ws/install/setup.bash
ros2 topic echo /decision_result
ros2 topic echo /response_result
ros2 topic echo /robot_action
```

정상 흐름에서는 `/decision_result`의 `response_key/response_args`가 `/response_result`의 `speech/display_text`로 변환되고, 이어서 `/robot_action`이 발행됩니다.
