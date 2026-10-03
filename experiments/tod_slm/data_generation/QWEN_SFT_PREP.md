# Pumpkin Qwen3 SFT 데이터 준비

이 문서는 규칙 검수까지 완료된 Pumpkin TOD 데이터를 Qwen3-0.6B LoRA SFT에 넣기 직전 형태로 만드는 3단계를 설명한다.

```text
28,872 train/valid 후보
        ↓
① canonical source group 기준 90/10 split
        ↓
Train 25,985 / Validation 2,887
        ↓
② Qwen messages JSONL 변환
        ↓
③ source-group leakage / 분포 / JSON schema 자동 검증

고정 Test 1,507은 그대로 유지
```

## 실행

저장소 루트에서:

```bash
python3 experiments/tod_slm/data_generation/prepare_qwen_sft.py
```

외부 Python 패키지는 필요하지 않는다.

## 1. source-group 기준 Train / Validation 분리

단순 row random split을 사용하지 않는다.

멀티턴 증강 데이터는 하나의 canonical source에서 다음처럼 여러 row가 만들어질 수 있다.

```text
structure_b_train_valid_020000
├── ..._ctx1
├── ..._ctx2
└── ..._ctx3
```

이 세 row가 train과 validation에 갈라지면 같은 사용자 원문이 양쪽에 나타나므로 validation 성능이 과대평가될 수 있다.

따라서 group key는 다음으로 고정한다.

```text
source.dataset + source.source_index
```

즉 canonical source 1개를 하나의 최소 분할 단위로 사용한다.

현재 28,872 row는 canonical source group **22,512개**에서 만들어졌으며 분할 결과는 다음과 같다.

```text
Train
- rows:          25,985
- source groups: 20,261

Validation
- rows:           2,887
- source groups:  2,251

Test
- rows:           1,507
- source groups:  1,507
```

실제 validation row 비율은 약 9.9993%다.

## 2. scenario-stratified group split

source group을 한꺼번에 random하게 10% 고르는 대신 source scenario family별로 약 10%씩 validation group을 고른다.

예:

```text
context::affirm                       320 groups → validation 32
context::cancel                       320 groups → validation 32
context::deny                         256 groups → validation 26
context::modify                       784 groups → validation 78
context::order_contextual_slot_answer 1500 groups → validation 150
order_complete                      12200 groups → validation 1220
order_missing_quantity              1000 groups → validation 100
order_missing_temperature            300 groups → validation 30
order_multi_complete                2500 groups → validation 250
...
```

선택 순서는 고정 seed + SHA-256 stable hash로 결정하므로 같은 데이터와 같은 seed에서는 항상 같은 split이 재현된다.

기본 seed:

```text
pumpkin-tod-v1-source-group-split-2026-09-03
```

## 3. 고정 test 정책

기존 최종 SFT test **1,507개를 재분할하지 않는다.**

```text
data/tod/pumpkin_tod_v1_sft_test.jsonl
```

을 그대로 읽어 Qwen chat 형식으로만 변환한다.

## 4. Qwen chat JSONL

출력 디렉터리:

```text
data/tod/qwen/
```

원래 TOD 구조를 보존한 split:

```text
pumpkin_tod_v1_train.jsonl
pumpkin_tod_v1_validation.jsonl
pumpkin_tod_v1_test.jsonl
```

Qwen 학습용 messages 형식:

```text
pumpkin_tod_v1_qwen_train.jsonl
pumpkin_tod_v1_qwen_validation.jsonl
pumpkin_tod_v1_qwen_test.jsonl
```

통계/검증 결과:

```text
pumpkin_tod_v1_qwen_stats.json
```

## 5. Qwen 한 row의 구조

각 row에는 학습에 필요한 `messages`와 데이터 추적용 metadata가 들어간다.

```json
{
  "id": "structure_b_train_valid_017000_ctx1",
  "source_group_id": "structure_b_train_valid:017000",
  "scenario_group": "order_contextual_slot_answer_multiturn",
  "split": "train",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "{...}"},
    {"role": "assistant", "content": "{...}"}
  ]
}
```

### system

Pumpkin TOD 모델의 역할과 안전 규칙을 설명한다.

핵심 규칙:

- 현재 user utterance와 이전 order state를 구분한다.
- 사용자가 말하지 않은 메뉴/온도/수량을 임의로 만들지 않는다.
- deterministic menu policy로 확정되는 값은 `state_after`에 반영할 수 있다.
- 출력은 JSON만 사용한다.
- 설명, Markdown, chain-of-thought를 출력하지 않는다.

### user

`content` 자체가 JSON 문자열이다.

```json
{
  "fsm_state_before": "ASK_QUANTITY",
  "state_before": {
    "items": [
      {
        "item_id": 0,
        "menu": "아메리카노",
        "temperature": "ICE",
        "quantity": null
      }
    ]
  },
  "history": [
    {
      "role": "assistant",
      "text": "아이스 아메리카노는 몇 잔 주문하시겠어요?"
    }
  ],
  "user_text": "두 잔이요"
}
```

### assistant

모델이 학습해야 할 정답도 JSON 문자열이다.

```json
{
  "intent": "ORDER",
  "utterance_items": [
    {
      "item_id": 0,
      "menu": null,
      "temperature": null,
      "quantity": 2
    }
  ],
  "state_after": {
    "items": [
      {
        "item_id": 0,
        "menu": "아메리카노",
        "temperature": "ICE",
        "quantity": 2
      }
    ]
  },
  "order_status": "VALID",
  "decision": "CONFIRM_ORDER",
  "response_key": "confirm_order",
  "fsm_state_after": "ORDER_CONFIRM",
  "response": "아이스 아메리카노 2잔 맞으신가요?"
}
```

`utterance_items`와 `state_after`를 분리하는 이유는 매우 중요하다.

```text
utterance_items = 이번 사용자 발화에서 실제로 표현한 것
state_after     = 이전 상태 + 이번 발화 + deterministic policy 적용 결과
```

따라서 모델이 사용자가 말하지 않은 slot을 발화 내용으로 꾸며내는 것을 평가할 수 있다.

## 6. Qwen3 thinking mode

데이터 파일 자체는 표준 Hugging Face `messages` 형태만 저장한다.

Qwen3 tokenizer로 실제 학습 문자열을 만들 때는 첫 baseline에서 thinking 출력을 쓰지 않는 방향이므로 다음 옵션을 사용한다.

```python
tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=False,
    enable_thinking=False,
)
```

실제 LoRA training script에서도 이 옵션을 동일하게 고정해야 한다.

## 7. 자동 leakage 검증

`prepare_qwen_sft.py`는 생성 직후 다음을 assert한다.

```text
train + validation rows = 28,872
test rows               = 1,507
final context_required  = 0
row ID 중복              = 0

Train ↔ Validation source group overlap = 0
Train ↔ Test source group overlap       = 0
Validation ↔ Test source group overlap  = 0
```

현재 결과:

```text
Train ↔ Validation = 0
Train ↔ Test       = 0
Validation ↔ Test  = 0
```

추가로 exact `user_text` overlap도 진단용으로 기록한다. 현재 세 split 사이 exact text overlap도 모두 0이지만, 이 값은 group key로 사용하지 않는다.

## 8. Qwen 변환 검증

각 Qwen row마다 다음도 검사한다.

- 원래 TOD row와 `id`가 같은가
- `source_group_id`가 올바른가
- role 순서가 정확히 `system → user → assistant`인가
- user content가 valid JSON인가
- assistant content가 valid JSON인가
- 변환된 user payload가 원래 state/history/user text와 동일한가
- 변환된 assistant payload가 원래 target과 동일한가

즉 chat 변환 과정에서 label이 조용히 바뀌면 생성 단계에서 즉시 실패한다.

## 9. 현재 학습에 사용할 파일

첫 Teacher-free Qwen3-0.6B LoRA baseline은 다음 파일을 사용한다.

```text
Train
 data/tod/qwen/pumpkin_tod_v1_qwen_train.jsonl

Validation
 data/tod/qwen/pumpkin_tod_v1_qwen_validation.jsonl

Test
 data/tod/qwen/pumpkin_tod_v1_qwen_test.jsonl
```

이 단계까지는 Teacher LLM을 사용하지 않는다.
