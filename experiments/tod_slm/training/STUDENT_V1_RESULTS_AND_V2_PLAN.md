# Pumpkin TOD Student v1 결과 및 Student v2 보강 계획

## 1. Student v1 학습 개요

- Base model: `Qwen/Qwen3-0.6B`
- Fine-tuning: LoRA SFT
- Teacher: 사용하지 않음
- External data: 사용하지 않음
- Assistant-only loss
- `enable_thinking=False`
- Train/validation/test source-group leakage: 0
- Train rows: 25,985
- Validation rows: 2,887
- Fixed test rows: 1,507
- Best checkpoint: `checkpoint-800`
- Best validation loss: `0.00016198483353946358`
- Best adapter path on school server: `outputs/tod_slm/qwen3_0.6b_lora_v1/best_adapter`

## 2. Fixed test 결과

고정 test 1,507개는 모델 선택/튜닝에 사용하지 않고 최종 일반화 성능 확인에 사용했다.

| Metric | Result |
| --- | ---: |
| JSON valid rate | 0.9993364299933643 |
| Intent accuracy | 0.9475779694757797 |
| Order status accuracy | 0.8911745189117452 |
| Decision accuracy | 0.8354346383543464 |
| Response key accuracy | 0.8354346383543464 |
| FSM state after accuracy | 0.8453881884538819 |
| State exact match | 0.7597876575978766 |
| Utterance items exact match | 0.7584605175846052 |
| State slot precision | 0.8984703632887189 |
| State slot recall | 0.9175942198789299 |
| State slot F1 | 0.9079316008115157 |
| Hallucinated slot count | 239 |
| Hallucinated slot opportunities | 1,409 |
| Hallucinated slot rate | 0.16962384669978708 |
| Response exact match | 0.7591240875912408 |

## 3. Error analysis 결과

- Invalid JSON rows: 1
- Any exact-match error rows: 432 / 1,507 (28.67%)
- Rows with slot hallucination: 159 / 1,507 (10.55%)
- Hallucinated slot assignments: 239

### Hallucinated slots

- `menu`: 109 (45.61%)
- `temperature`: 74 (30.96%)
- `quantity`: 56 (23.43%)

### Hallucination rows by gold decision

- `ASK_MENU`: 43 (27.04%)
- `ASK_QUANTITY`: 40 (25.16%)
- `ASK_TEMPERATURE`: 33 (20.75%)
- `CONFIRM_ORDER`: 23 (14.47%)
- `OUT_OF_POLICY`: 20 (12.58%)

### Decision-family error rates

- `ASK_MENU`: 56/56 (100.00%)
- `REORDER_REQUEST`: 16/18 (88.89%)
- `ASK_TEMPERATURE`: 47/136 (34.56%)
- `CONFIRM_ORDER`: 189/616 (30.68%)
- `ASK_QUANTITY`: 71/240 (29.58%)
- `GUIDE_CUSTOMER`: 14/48 (29.17%)
- `CANCEL_ORDER`: 12/62 (19.35%)
- `OUT_OF_POLICY`: 21/159 (13.21%)
- `MODIFY_ORDER`: 4/92 (4.35%)
- `ORDER_CONFIRMED`: 2/80 (2.50%)

### Top decision confusions

- `CONFIRM_ORDER -> ASK_QUANTITY`: 54
- `ASK_MENU -> CONFIRM_ORDER`: 21
- `OUT_OF_POLICY -> ASK_QUANTITY`: 20
- `ASK_MENU -> ASK_QUANTITY`: 18
- `ASK_QUANTITY -> ASK_TEMPERATURE`: 16
- `GUIDE_CUSTOMER -> OUT_OF_POLICY`: 14
- `CONFIRM_ORDER -> ASK_TEMPERATURE`: 13
- `ASK_MENU -> OUT_OF_POLICY`: 11
- `CONFIRM_ORDER -> MODIFY_ORDER`: 11
- `ASK_QUANTITY -> CONFIRM_ORDER`: 10
- `REORDER_REQUEST -> MODIFY_ORDER`: 9
- `ASK_TEMPERATURE -> CONFIRM_ORDER`: 8

## 4. 핵심 해석

Student v1은 기본 의도 분류와 슬롯 추출 능력은 충분히 확보했다. 특히 Intent accuracy 94.76%, State slot F1 90.79%로 기본 주문 이해 능력은 양호하다.

하지만 실제 로봇 주문 흐름에서 중요한 다음 문제가 확인되었다.

1. 정보가 없는 슬롯을 임의로 채우는 hallucination
2. missing-slot 상황에서 `ASK_*` 대신 `CONFIRM_ORDER` 등으로 잘못 이동
3. `ASK_MENU`의 완전한 미학습
4. `REORDER_REQUEST` 일반화 실패
5. `CONFIRM_ORDER`와 `ASK_QUANTITY`/`ASK_TEMPERATURE` 경계 혼동

특히 `ASK_MENU`는 train/validation에 존재하지 않고 fixed test에만 56개가 존재했다. 따라서 56/56 실패는 단순 epoch 부족보다 데이터 커버리지 부족의 영향이 크다고 판단한다.

## 5. Student v2 보강 우선순위

### Priority 1. ASK_MENU 신규 학습군

목표: 메뉴가 명시되지 않았을 때 메뉴를 추측하지 않고 `menu=null`을 유지하고 `ASK_MENU`로 결정한다.

권장 신규 데이터: 약 800~1,200개

예:

- 사용자: `아이스로 두 잔 주세요.`
- `menu=null`
- `temperature=ICE`
- `quantity=2`
- decision: `ASK_MENU`

### Priority 2. Anti-hallucination / missing-slot 강화

사용자가 명시하지 않은 값은 절대 추론하여 채우지 않는다.

권장 신규 데이터:

- ASK_QUANTITY: 500~800
- ASK_TEMPERATURE: 500~800
- multi-order partial missing slots: 800~1,200

원칙:

- 말하지 않은 메뉴 → `null`
- 말하지 않은 온도 → `null`
- 말하지 않은 수량 → `null`
- `state_after`는 이전 state + 실제 발화 정보 + deterministic policy만 반영

### Priority 3. Hard decision boundary

권장 신규 데이터:

- `CONFIRM_ORDER` hard cases: 500~800
- `REORDER_REQUEST`: 300~500
- `UNKNOWN/GUIDE/OUT_OF_POLICY` 경계: 300~500

총 추가량 권장: 약 4,000~5,500개의 신규 hard-case SFT rows.

## 6. 중요한 평가 원칙

이번 fixed test 1,507개는 이미 최종 평가에 사용했다.

따라서 Student v2를 만들 때 다음을 금지한다.

- fixed test 문장을 그대로 train에 추가
- fixed test gold JSON을 그대로 train label로 재사용
- fixed test 성능을 보고 learning rate/epoch 등 hyperparameter를 직접 튜닝

허용되는 것은 오류의 **유형**을 참고해 새 문장/새 source group을 생성하는 것이다.

Student v2에서는 새 hard-case 데이터를 train/validation에 추가하고, 필요하면 장기적으로 별도의 새로운 held-out test를 추가해 v2 성능을 평가한다.

## 7. 학교 서버에서 보존해야 할 산출물

학교 서버 사용 종료 전에 최소 아래를 로컬에 백업한다.

```text
outputs/tod_slm/qwen3_0.6b_lora_v1/best_adapter/
outputs/tod_slm/qwen3_0.6b_lora_v1/evaluation/test_metrics.json
outputs/tod_slm/qwen3_0.6b_lora_v1/evaluation/test_predictions.jsonl
outputs/tod_slm/qwen3_0.6b_lora_v1/evaluation/error_analysis/
experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml
```

`best_adapter`는 LoRA adapter이므로 이것만으로 standalone base model 전체가 되는 것은 아니다. 추론할 때는 `Qwen/Qwen3-0.6B` base model과 함께 로드한다. 학교 서버의 Hugging Face cache 전체를 반드시 백업할 필요는 없으며, 인터넷이 가능한 환경에서는 base model을 다시 다운로드할 수 있다.

## 8. 다음 작업 재개 시 체크리스트

1. Student v1 adapter와 fixed test 결과 보존 확인
2. `test_error_report.json` 및 grouped examples 검토
3. 새 hard-case source 데이터 생성
4. `ASK_MENU` train/validation coverage 추가
5. anti-hallucination 규칙 적용
6. source-group-safe split 재생성
7. Student v2 LoRA 학습
8. validation으로 모델 선택
9. 별도 held-out evaluation 전략 결정
10. 성능 확인 후 Jetson Orin Nano runtime 통합
