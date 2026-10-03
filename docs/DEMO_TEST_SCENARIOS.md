# Pumpkin 시연 반복 테스트 시나리오

목적: 실제 로봇 시연 환경에서 STT → NLU → FSM/Decision → TTS/동작 문제를 빠르게 재현하고, `scripts/run_robot_debug.sh`의 핵심 로그만으로 원인을 분리한다.

## 실행

```bash
cd ~/pumpkin
git pull
bash scripts/run_robot_debug.sh
```

최근 요약 로그:

```bash
cat /tmp/pumpkin-logs/demo_debug_latest.log
```

각 시나리오는 한 번 성공했다고 끝내지 말고 최소 3회 반복한다. 실패하면 전체 원본 로그보다 먼저 `demo_debug_latest.log`를 공유한다.

## 테스트 순서

### P0. 시연 전에 반드시 통과해야 하는 핵심 시나리오

| ID | 입력/행동 | 기대 결과 | 주요 확인 지점 |
|---|---|---|---|
| S01 | `아이스 아메리카노 한 잔 주세요` → 확인 질문에 `네` | 한 번에 메뉴/온도/수량을 추출하고 주문 확인 후 완료 | `STT TEXT`, `NLU items=[아메리카노/ICE/1]`, `CONFIRM_ORDER`, `ORDER_CONFIRMED` |
| S02 | `아이스 두 잔 주세요` → `아메리카노요` | 메뉴만 재질문하고 기존 ICE/2를 유지 | `missing=menu`, 다음 TURN에서 기존 슬롯 보존 |
| S03 | `아메리카노 한 잔 주세요` → `따뜻하게요` | 온도만 재질문하고 HOT으로 채운 뒤 확인 | `missing=temperature`, 최종 HOT |
| S04 | `아이스 카페라떼 주세요` → `두 잔이요` | 수량만 재질문하고 2잔으로 채움 | `missing=quantity`, 최종 quantity=2 |
| S05 | `아이스 카페라떼 주세요` → 수량 질문 때 손가락 3개 | 음성 없이 수량 3을 반영 | `GESTURE hand=THREE_FINGERS`, Decision의 수량=3 |
| S06 | 완성 주문 확인 질문에 고개 끄덕임 | NOD를 `네`와 동일하게 처리하고 주문 확정 | `GESTURE head=NOD`, `ORDER_CONFIRMED` |
| S07 | 완성 주문 확인 질문에 `아니요` → `두 잔으로 바꿔주세요` | 수정 모드 진입 후 수량 변경, 다시 확인 | `MODIFY_ORDER`, 수정 후 `CONFIRM_ORDER` |
| S08 | `아이스 아메리카노 한 잔하고 따뜻한 카페라떼 두 잔 주세요` | 두 주문 항목의 메뉴/온도/수량 관계를 각각 정확히 유지 | NLU `#1`, `#2` 항목 대응관계 |
| S09 | 첫 주문 확인 중 `딸기스무디 한 잔도 추가해 주세요` | 기존 주문을 지우지 않고 새 항목 추가 후 전체 재확인 | `reason=additional_order_appended`, items 2개 |
| S10 | 진행 중 `주문 취소할게요` | 현재 주문 초기화 후 IDLE | `CANCEL_ORDER`, 이전 주문이 다음 세션에 남지 않음 |

### P1. 누락 슬롯과 멀티턴 안정성

| ID | 입력/행동 | 기대 결과 | 주요 확인 지점 |
|---|---|---|---|
| S11 | `아메리카노랑 라떼 하나씩 주세요` → `따뜻하게요` → `아이스요` | 첫 메뉴 온도, 다음 메뉴 온도를 순서대로 질문 | `waiting item=0 temperature` → `item=1 temperature` |
| S12 | `아메리카노랑 라떼 하나씩 주세요` → `둘 다 아이스로요` | 두 항목에 ICE를 동시에 적용 | 두 item 모두 ICE |
| S13 | `아이스 두 잔 주세요` → 메뉴 질문에 `카페라떼요` | 기존 수량/온도를 보존하면서 메뉴만 보충 | slot merge 정상 여부 |
| S14 | 수량 질문 중 `글쎄요` → `모르겠어요` → `뭐라고요` | 두 번 재질문 후 재시작 | `REPROMPT` 2회 → `REORDER_REQUEST`, `slot_retry_exhausted` |
| S15 | 처음 입력에서 `음` → `저기` → `모르겠어` | 저신뢰도 입력이 무한 반복되지 않고 재시작 | `low_conf`, 최종 `nlu_retry_exhausted` |

### P1. STT 실물 환경 문제

| ID | 입력/행동 | 기대 결과 | 주요 확인 지점 |
|---|---|---|---|
| S16 | 로봇이 말하는 동안 사용자는 침묵 | 로봇 자신의 TTS가 사용자 발화로 다시 들어오지 않음 | TTS 문장과 동일한 `STT TEXT`가 생기면 실패 |
| S17 | 로봇 TTS 종료 직후 바로 `네` | 대기시간 때문에 빠른 응답을 놓치지 않음 | `listening` 전환 후 `네`가 STT에 잡히는지 |
| S18 | 평소보다 작은 목소리로 주문 | 너무 작으면 명확히 재질문하고, 엉뚱한 주문을 확정하지 않음 | `STT=too_quiet` 또는 정상 transcript |
| S19 | 일부러 잠깐 침묵만 유지 | 잘못된 가짜 문장을 만들지 않고 재질문 | `STT=no_speech`, 주문 state 오염 없음 |
| S20 | `카페라떼 하나 주세요`를 5회 반복 | 실제 문제 메뉴명의 STT 안정성 확인 | `STT TEXT`가 `카페라떼` 계열로 얼마나 일관적인지 |

### P1. 정책/예외 처리

| ID | 입력/행동 | 기대 결과 | 주요 확인 지점 |
|---|---|---|---|
| S21 | `카푸치노 한 잔 주세요` | 지원하지 않는 메뉴로 임의 변환하지 않고 다시 주문 요청 | `OUT_OF_POLICY`, `unsupported_menu` |
| S22 | `따뜻한 딸기스무디 한 잔 주세요` | HOT 딸기스무디를 확정하지 않고 아이스 전용 안내 | `unsupported_temperature_for_menu` |
| S23 | `따뜻한 레몬에이드 두 잔 주세요` | HOT 레몬에이드 거부 | 동일 |
| S24 | 수량 질문이 아닌 상태에서 손가락 2개 | 주문 수량이 바뀌지 않아야 함 | gesture가 보여도 Decision 변화 없음 |
| S25 | 주문 확인 중 V 사인 등 일상 손동작 | 수량으로 오인하지 않아야 함 | `ORDER_CONFIRM` 유지 |

### P2. 세션/사람 감지 안정성

| ID | 입력/행동 | 기대 결과 | 주요 확인 지점 |
|---|---|---|---|
| S26 | 주문 진행 중 몸을 잠깐 카메라 밖으로 뺐다가 복귀 | 진행 중 주문이 갑자기 초기화되거나 인사부터 재시작하지 않음 | active order 중 presence 변화가 informational인지 |
| S27 | 주문 완료 후 카메라에서 완전히 나갔다가 다시 등장 | 새 고객 세션으로 시작, 이전 주문 없음 | 새 greeting, 이전 `current_order` 잔존 금지 |
| S28 | 연속으로 서로 다른 주문 3건 수행 | 앞 주문의 메뉴/수량/온도가 다음 주문에 섞이지 않음 | TURN별 session reset |

## 시연 전 최소 합격 기준

- S01~S10은 모두 통과.
- S01, S03, S04, S08, S16, S17, S20은 각각 3회 연속 성공.
- 손가락 수량을 시연에 넣는 경우 S05, S24, S25도 3회 연속 성공.
- 실패 시 `⚠ PROBLEM` 또는 `❌ ERROR`가 어느 단계에서 처음 발생했는지 기록.

## 실패 기록 양식

```text
시나리오: S__
내가 실제로 한 말/행동:
로봇이 실제로 한 말/행동:
재현 횟수: __/3

문제가 처음 보인 단계:
[ ] STT
[ ] NLU
[ ] FSM/Decision
[ ] TTS
[ ] Vision/Gesture
[ ] Action

demo_debug_latest.log:
(여기에 그대로 붙여넣기)
```

## 빠른 판정법

- `STT TEXT`부터 틀리면 STT/VAD/마이크 문제.
- `STT TEXT`는 맞는데 `NLU items`가 틀리면 NLU/후처리 문제.
- NLU가 맞는데 `FSM reason` 또는 `missing`이 이상하면 Decision/FSM 문제.
- Decision이 맞는데 `ROBOT SAY`가 이상하면 Response Manager 문제.
- `ROBOT SAY`는 맞는데 실제 소리가 없으면 TTS/오디오 문제.
- `ACTION`은 맞는데 실제 목/팔/LCD가 다르면 하드웨어 실행부 문제.

이 문서는 자동 단위테스트가 아니라 실제 시연 직전 반복 검증용 수동 시나리오이다. 코드 회귀는 기존 `test_dialogue_pipeline_scenarios.py`, `test_hand_quantity_gesture_flow.py`, `test_additional_order_during_confirmation.py`, `test_s8_order_exception_flow.py`를 함께 사용한다.
