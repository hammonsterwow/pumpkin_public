# Pumpkin TOD 데이터 생성 파이프라인

이 디렉터리는 현재 canonical Structure B NLU 데이터 **24,019개**를 새 Task-Oriented Dialogue(TOD) 학습 형식으로 변환하고, 이전 대화가 필요한 샘플에는 안전한 멀티턴 문맥을 자동으로 붙인다.

> **데이터 관리 정책:** canonical Structure B 데이터와 최종 Qwen 학습용 `*_qwen_train.jsonl`, `*_qwen_validation.jsonl`, `*_qwen_test.jsonl`, 통계·검수 결과를 버전 관리합니다. 파이프라인으로 재생성할 수 있는 `pumpkin_tod_v1_train_valid`, `multiturn`, `sft` 계열 중간 JSONL은 저장하지 않습니다.

핵심 원칙은 다음과 같다.

- 학습된 NLU 모델의 prediction을 새 정답으로 사용하지 않는다.
- canonical JSONL의 ground truth를 source of truth로 사용한다.
- 주문 상태와 다음 행동은 현재 Pumpkin 메뉴 정책/FSM 규칙으로 결정한다.
- 응답은 현재 `ResponseManager`에서 생성한다.
- 사용자가 말하지 않은 슬롯을 임의로 사실처럼 만들지 않는다.
- 멀티턴 문맥을 만들 때도 LLM을 라벨 생성기로 사용하지 않는다.

## 입력

```text
data/structure_b_train_valid.jsonl   22,512
data/structure_b_test.jsonl           1,507
-------------------------------------------
합계                                  24,019
```

## 1단계: 규칙 기반 TOD 라벨 생성

실행:

```bash
python3 experiments/tod_slm/data_generation/generate_rule_labels.py
```

출력:

```text
data/tod/
├── pumpkin_tod_v1_train_valid.jsonl
├── pumpkin_tod_v1_test.jsonl
└── pumpkin_tod_v1_stats.json
```

이 단계에서 `text`, `intent`, `items`, `order_status`에 다음 정보를 추가한다.

```text
utterance_items
state_before
state_after
fsm_state_before
fsm_state_after
decision
response_key
response
```

### 주문 슬롯 질문 규칙

현재 `DecisionNode.SLOT_PRIORITY`와 동일하게:

```text
menu → quantity → temperature
```

순으로 확인한다. 여러 음료가 있으면 한 item을 완성한 뒤 다음 item으로 이동한다.

### ICE-only 메뉴

현재 메뉴 정책상:

```text
레몬에이드  → ICE only
딸기스무디 → ICE only
```

이므로 runtime state에서는 정책으로 ICE가 채워질 수 있다. 하지만 사용자가 실제로 ICE라고 말하지 않았다면 `utterance_items.temperature`는 `null`로 유지하고, 정책 추론값은 `target.inferred_policy_slots`에 기록한다.

### 1단계 결과

```text
전체                         24,019
fully supervised             20,259
context required              3,760
```

문맥이 필요한 데이터는 다음과 같다.

```text
AFFIRM                         400
DENY                           320
MODIFY                         980
CANCEL                         400
메뉴 없는 contextual ORDER   1,660
---------------------------------
합계                         3,760
```

이 3,760개에는 이전 주문 상태를 모르는 상태에서 가짜 `state_after`나 `response`를 붙이지 않는다.

## 2단계: 멀티턴 문맥 자동 생성

실행:

```bash
python3 experiments/tod_slm/data_generation/build_multiturn_scenarios.py
```

이 스크립트는 1단계에서 `context_required=true`로 남겨둔 샘플을 자동으로 완성한다.

예를 들어 원본이:

```text
사용자: 두 잔이요
```

라면 단독으로는 어떤 메뉴의 두 잔인지 알 수 없으므로 1단계에서는 partial label로 남긴다.

2단계에서는 다음처럼 현재 메뉴 정책에 맞는 이전 상태를 만든다.

```text
state_before:
아이스 카페라떼 / 수량 미정

history:
로봇: 아이스 카페라떼는 몇 잔 주문하시겠어요?

사용자:
두 잔이요

state_after:
아이스 카페라떼 / 2잔

next decision:
CONFIRM_ORDER
```

응답도 직접 작성하지 않고 현재 `ResponseManager`를 사용해 생성한다.

```text
아이스 카페라떼 2잔 맞으신가요?
```

### AFFIRM

```text
로봇: 따뜻한 아메리카노 1잔 맞으신가요?
사용자: 네 맞아요
→ ORDER_CONFIRMED
→ 주문이 확정되었습니다. 감사합니다.
```

### DENY

```text
로봇: 아이스 카페라떼 2잔 맞으신가요?
사용자: 아니요
→ MODIFY_ORDER
→ 어떤 부분을 바꿀까요?
```

### MODIFY

```text
state_before:
따뜻한 바닐라라떼 2잔

사용자:
아메리카노로 수정해주세요

state_after:
따뜻한 아메리카노 2잔

→ CONFIRM_ORDER
```

명시적으로 수정하지 않은 온도/수량은 이전 주문 상태에서 유지한다.

### CANCEL

취소는 최종 확인 상태뿐 아니라 활성 주문 도중에도 발생할 수 있으므로 train 데이터에서는 다음 상태를 섞는다.

```text
ORDER_CONFIRM
ASK_QUANTITY
ASK_TEMPERATURE
```

모두:

```text
→ CANCEL_ORDER
→ state_after.items = []
```

으로 처리한다.

### 온도 답변 문맥 안전 규칙

`아이스요`, `따뜻하게요` 같은 온도 답변에는 반드시 **ICE/HOT을 둘 다 지원하는 메뉴**만 이전 문맥으로 사용한다.

레몬에이드나 딸기스무디처럼 ICE-only인 메뉴는 시스템 정책이 질문 전에 이미 ICE를 확정하기 때문에 `ASK_TEMPERATURE` 문맥을 만들면 안 된다.

## 데이터 증강 정책

train/valid의 context-required source row는 각각 **3개 문맥**을 생성한다.

```text
3,180 source rows × 3 = 9,540 multi-turn rows
```

test는 같은 source utterance가 여러 번 반복되어 평가 비중이 왜곡되지 않도록 **각 source row당 1개만 생성**한다.

```text
580 source rows × 1 = 580 multi-turn rows
```

## 최종 SFT 데이터

2단계 실행 후 다음 파일이 생성된다.

```text
data/tod/
├── pumpkin_tod_v1_multiturn_train_valid.jsonl
├── pumpkin_tod_v1_multiturn_test.jsonl
├── pumpkin_tod_v1_sft_train_valid.jsonl
├── pumpkin_tod_v1_sft_test.jsonl
├── pumpkin_tod_v1_multiturn_review_sample.jsonl
└── pumpkin_tod_v1_multiturn_stats.json
```

최종 크기:

```text
train/valid
기존 fully supervised      19,332
새 multi-turn               9,540
--------------------------------
최종 SFT                   28,872

 test
기존 fully supervised         927
새 multi-turn                 580
--------------------------------
최종 test                   1,507
```

최종 SFT 파일에는 `context_required=true` 샘플이 **0개**다.

## 생성된 멀티턴 분포

train/valid 기준:

```text
AFFIRM                    960
CANCEL                    960
DENY                      768
MODIFY                  2,352
contextual ORDER        4,500
-----------------------------
합계                    9,540
```

MODIFY 2,352개 중 일부는 슬롯을 직접 바꾸는 문장이고, 일부는 `수정할게요`처럼 변경 내용을 추가로 물어봐야 하는 문장이다.

## 자동 검증

멀티턴 builder는 다음을 검사한다.

- 생성된 `history`가 존재하는가
- `state_before`가 실제 활성 주문인가
- 이전 주문이 메뉴 정책상 `INVALID`가 아닌가
- `state_after`가 존재하는가
- `decision`, `response_key`, `response`가 모두 존재하는가
- 최종 SFT 데이터에 `context_required=true`가 남아 있지 않은가
- test가 정확히 1,507개로 유지되는가

GitHub Actions에서도 같은 검증을 수행한다.

현재 생성 결과의 `validation_error_count`는 train/valid와 test 모두 **0**이다.

## 사람 검수는 3,760개 전체가 필요하지 않다

자동 생성 후 다음 파일에 **200개 표본**을 따로 만든다.

```text
data/tod/pumpkin_tod_v1_multiturn_review_sample.jsonl
```

구성은 context source scenario별 40개씩이다.

```text
AFFIRM                  40
CANCEL                  40
DENY                    40
MODIFY                  40
contextual ORDER        40
---------------------------
합계                   200
```

사람은 이 표본에서 다음 네 가지만 확인하면 된다.

1. `state_before`가 사용자 발화와 자연스럽게 연결되는가
2. user utterance의 기존 ground-truth 슬롯이 그대로 유지되는가
3. `state_after`가 규칙상 올바른가
4. `decision`과 `response`가 서로 모순되지 않는가

문제가 발견되면 개별 JSON을 손으로 고치는 대신 **scenario builder 규칙을 수정하고 전체 데이터를 다시 생성**한다.

## 최종 학습에 사용할 파일

Qwen SFT의 첫 실험에서는 다음 두 파일을 사용한다.

```text
학습/검증 후보:
data/tod/pumpkin_tod_v1_sft_train_valid.jsonl

고정 test:
data/tod/pumpkin_tod_v1_sft_test.jsonl
```

다음 단계에서 `pumpkin_tod_v1_sft_train_valid.jsonl`을 실제 train/validation으로 다시 분리할 때는 단순 random row split보다 **source/template/scenario family 단위 split**을 권장한다. 같은 원문에서 만든 `ctx1/ctx2/ctx3`가 서로 train과 validation에 흩어지면 평가 점수가 과대평가될 수 있기 때문이다.

## Teacher 모델을 붙이는 시점

Teacher LLM은 이 규칙 기반 라벨 이후에 사용한다.

Teacher에게 맡길 것:

```text
response 자연화
동일 의미의 다양한 표현 생성
어려운 사용자 발화 paraphrase 생성
```

Teacher에게 맡기지 않을 것:

```text
menu 정답 결정
temperature 정답 결정
quantity 정답 결정
state_before/state_after 결정
FSM decision 결정
```

즉 주문의 사실과 상태 전이는 deterministic rule/FSM이 책임지고, Teacher는 주로 자연어 표현을 풍부하게 만드는 역할만 맡긴다.
