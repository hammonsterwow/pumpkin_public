# Item Query NLU 비교 실험

Pumpkin 주문 NLU에서 복수 메뉴를 항목별로 구조화하는 방식을 비교한 실험 코드입니다. KoELECTRA-small encoder를 공통으로 사용하고, Independent Item Heads와 Item Query Decoder의 차이 및 학습 전략 적용에 따른 성능 변화를 같은 데이터 조건에서 확인합니다.

## 데이터셋

- train/validation pool: `data/structure_b_train_valid.jsonl` — 22,512개
- test: `data/structure_b_test.jsonl` — 1,507개
- test set은 최종 평가에만 사용합니다.

분할 기준:

- single: `template_id` family
- multi: `item_count + source.category`
- followup: `source.category`
- 관련 메타데이터가 없으면 intent/item-count 기준으로 분할

## 비교 구성

| ID | 구성 | 비교 목적 |
|---|---|---|
| M0 | KoELECTRA-small + Independent Item Heads | Item Query Decoder를 사용하지 않는 기준 구조 |
| M1 | KoELECTRA-small + Item Query Decoder | Item Query 구조 자체의 효과 확인 |
| M2 | M1 + differential LR + multi-order oversampling + weighted loss | 학습 전략을 함께 적용한 개선 구성 |

공통 설정:

- Encoder: `monologg/koelectra-small-v3-discriminator`
- max input length: 96
- max items: 3
- seeds: 42, 43, 44
- 동일한 train/validation/test split과 label space 사용

## Ablation

개선 요소의 영향을 확인하기 위해 다음 순서로 cumulative ablation을 구성합니다.

| ID | 구성 |
|---|---|
| A0 | Item Query |
| A1 | A0 + differential LR |
| A2 | A1 + multi-order oversampling |
| A3 | A2 + weighted loss |
| A4 | A3 + R-Drop |

M2와 A3는 동일한 설정입니다.

## 실행

Colab에서는 `kips_item_query_experiments_colab.ipynb`를 사용합니다.

1. GPU 런타임을 선택합니다.
2. `RUN_MAIN_EXPERIMENTS=True`로 M0/M1/M2를 실행합니다.
3. 각 모델을 seeds 42/43/44로 학습합니다.
4. ablation이 필요하면 `RUN_ABLATION=True`로 실행합니다.
5. R-Drop은 `RUN_RDROP=True`일 때만 실행합니다.

개별 노트북:

- `01_M0_independent_heads.ipynb`
- `02_M1_item_query.ipynb`
- `03_M2_improved_item_query.ipynb`
- `04_ablation.ipynb`

## 평가 지표

복수 주문에서는 메뉴별 slot 조합이 모두 맞는지가 중요하므로 Exact Match 계열 지표를 중심으로 확인합니다.

- `order_exact_match`
- `single_item_em`
- `two_item_em`
- `three_item_em`
- `multi_item_em`
- `frame_accuracy`
- `intent_macro_f1`
- `menu_accuracy`
- `temperature_accuracy`
- `quantity_accuracy`
- `item_active_accuracy`

## 결과 파일

```text
kips_2026_results/
├── runs/<experiment>_seed<seed>/
│   ├── best_model.pt
│   ├── history.csv
│   ├── test_predictions.csv
│   └── test_errors.csv
├── main_runs.csv
├── main_summary.csv
├── paper_main_table.csv
├── ablation_runs.csv
├── ablation_summary.csv
└── experiment_manifest.json
```

모델 선택은 validation 결과로 수행하며, 최종 비교는 3개 seed의 평균과 표준편차를 사용합니다.
