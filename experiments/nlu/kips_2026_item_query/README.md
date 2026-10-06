# KIPS 2026 Item Query NLU 실험

이 폴더는 KIPS 학부생 논문용 NLU 비교 실험을 재현하기 위한 실행 패키지입니다.

## 1. 연구 질문

> KoELECTRA-small 기반 한국어 카페 주문 NLU에서 Item Query Decoder가 독립적인 item head 방식보다 복수 주문의 항목별 구조화 성능을 향상시키는가? 또한 데이터 불균형과 학습 전략을 보정하면 추가 향상이 있는가?

## 2. 고정 데이터셋

모든 모델은 반드시 같은 데이터와 같은 split을 사용합니다.

- 학습/검증 pool: `data/structure_b_train_valid.jsonl` — 22,512개
- 최종 test: `data/structure_b_test.jsonl` — 1,507개

`structure_b_test.jsonl`은 학습, hyperparameter 선택, threshold 조정에 사용하지 않습니다. 각 run에서 validation으로 best checkpoint를 선택한 뒤 마지막 평가에만 사용합니다.

노트북은 기존 Structure B 실험 원칙을 따라 train/validation을 분할합니다.

- single: `template_id` family 단위 분할을 우선 사용
- multi: `item_count + source.category` 기준 층화 분할
- followup: `source.category` 기준 층화 분할
- 위 메타데이터가 없는 레코드는 intent/item-count 기반 fallback split 사용

## 3. 메인 실험: 9 training runs

공통 조건:

- Encoder: `monologg/koelectra-small-v3-discriminator`
- max input length: 96
- max item queries/items: 3
- seeds: 42, 43, 44
- 동일 train/validation/test split
- 동일 label space 및 evaluation code

| ID | 모델 | 차이 | 목적 |
|---|---|---|---|
| M0 | KoELECTRA-small + Independent Item Heads | Item Query/Transformer Decoder 없음 | 구조 baseline |
| M1 | KoELECTRA-small + Item Query Decoder | 기존 학습 방식 | Item Query 자체 효과 |
| M2 | M1 + improved training | differential LR + multi-order oversampling + weighted loss | 최종 제안 모델 |

따라서 메인 논문 결과는 `3 configurations × 3 seeds = 9 runs`입니다.

## 4. Ablation은 무엇인가?

Ablation은 최종 성능 향상이 어떤 요소 때문에 생겼는지 하나씩 추가/제거하면서 확인하는 실험입니다.

이 폴더의 cumulative ablation 순서는 다음과 같습니다.

| ID | 구성 | 확인 내용 |
|---|---|---|
| A0 | Item Query 기본형 | 기준 |
| A1 | A0 + differential LR | encoder/decoder LR 분리 효과 |
| A2 | A1 + multi-order oversampling | 2/3-item 학습 강화 효과 |
| A3 | A2 + weighted loss | intent/item-active 불균형 보정 효과 |
| A4 | A3 + R-Drop (선택) | regularization 추가 효과 |

처음에는 `ABLATION_SEEDS = [42]`로 빠르게 스크리닝합니다. 논문 본문에 ablation 표를 넣기로 결정한 경우에만 `[42, 43, 44]`로 다시 실행하여 평균±표준편차를 계산하는 것을 권장합니다.

중요: M2는 A3와 동일한 설정입니다. 따라서 main M2 결과를 ablation A3 결과로 재사용할 수 있습니다.

## 5. 평가 지표

메인 지표는 주문 전체 구조가 정확히 맞았는지를 보는 Exact Match입니다.

- `order_exact_match`: ORDER 문장의 모든 item/slot을 정확히 맞힌 비율
- `single_item_em`: 정답 item이 1개인 ORDER 문장 Exact Match
- `two_item_em`: 정답 item이 2개인 ORDER 문장 Exact Match
- `three_item_em`: 정답 item이 3개인 ORDER 문장 Exact Match
- `multi_item_em`: 2-item + 3-item Exact Match
- `frame_accuracy`: intent/status/item 구조 전체 frame 정확도
- `intent_macro_f1`
- `menu_accuracy`
- `temperature_accuracy`
- `quantity_accuracy`
- `item_active_accuracy`

논문에서 가장 중요한 표는 `1-item / 2-item / 3-item / Overall order EM`입니다.

## 6. 실행 순서

1. Colab에서 GPU 런타임을 선택합니다.
2. `kips_item_query_experiments_colab.ipynb`를 엽니다.
3. `RUN_MAIN_EXPERIMENTS=True`, `RUN_ABLATION=False`, `RUN_RDROP=False` 상태로 실행합니다.
4. `structure_b_train_valid.jsonl`, `structure_b_test.jsonl` 두 파일을 업로드합니다. 저장소를 clone/mount한 경우 경로 모드도 사용할 수 있습니다.
5. M0, M1, M2를 seeds 42/43/44로 실행합니다. 총 9회 학습입니다.
6. notebook이 `main_runs.csv`, `main_summary.csv`, `paper_main_table.csv`를 생성합니다.
7. 필요하면 `RUN_ABLATION=True`로 바꾸고 A0→A3를 실행합니다. 처음에는 seed 42 하나만 권장합니다.
8. R-Drop까지 보고 싶을 때만 `RUN_RDROP=True`로 설정합니다.
9. 논문에 사용할 최종 수치는 `paper_main_table.csv`와 `ablation_summary.csv`에서 가져옵니다.

## 7. 결과 파일

노트북 실행 시 `kips_2026_results/` 아래에 생성됩니다.

```text
kips_2026_results/
├── runs/
│   └── <experiment>_seed<seed>/
│       ├── best_model.pt
│       ├── history.csv
│       ├── test_predictions.csv
│       └── test_errors.csv
├── main_runs.csv
├── main_summary.csv
├── paper_main_table.csv
├── ablation_runs.csv
├── ablation_summary.csv
└── experiment_manifest.json
```


## 9. 주의

- test set을 보면서 learning rate, loss weight, oversampling ratio를 바꾸지 않습니다.
- 모델 선택은 validation 결과로만 합니다.
- M0/M1/M2에서 데이터 split과 seed는 동일하게 유지합니다.
- 논문에 수치를 옮길 때 한 번의 최고값이 아니라 3 seeds 평균±표준편차를 사용합니다.
- R-Drop은 필수가 아닙니다. 계산량이 거의 2배가 되므로 메인 9회 실험이 끝난 뒤 선택적으로 실행합니다.
