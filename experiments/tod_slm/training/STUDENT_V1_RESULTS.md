# Pumpkin TOD Student v1 결과

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

## 5. 평가 원칙

고정 test 1,507개는 최종 일반화 성능 평가에만 사용하며, 학습 데이터 구성이나 하이퍼파라미터 조정에 사용하지 않습니다.

- fixed test 문장을 학습 데이터에 추가하지 않습니다.
- fixed test의 정답 JSON을 학습 라벨로 재사용하지 않습니다.
- fixed test 성능을 기준으로 learning rate나 epoch를 직접 조정하지 않습니다.
- 후속 실험에서는 새로운 train/validation 데이터와 별도의 held-out test를 사용합니다.
