# KIPS 2026 Item Query NLU 실험

KoELECTRA-small 기반 한국어 카페 주문 NLU에서 Item Query Decoder의 복수 주문 구조화 성능을 비교한 실험 코드입니다.

## 데이터셋

- train/validation pool: `data/structure_b_train_valid.jsonl` — 22,512개
- test: `data/structure_b_test.jsonl` — 1,507개
- test set은 최종 평가에만 사용합니다.

분할 기준:

- single: `template_id` family
- multi: `item_count + source.category`
- followup: `source.category`
- 관련 메타데이터가 없으면 intent/item-count 기준으로 분할

## 비교 모델

| ID | 구성 |
|---|---|
| M0 | KoELECTRA-small + Independent Item Heads |
| M1 | KoELECTRA-small + Item Query Decoder |
| M2 | M1 + differential LR + multi-order oversampling + weighted loss |

공통 설정:

- Encoder: `monologg/koelectra-small-v3-discriminator`
- max input length: 96
- max items: 3
- seeds: 42, 43, 44
- 동일한 train/validation/test split과 label space 사용

## Ablation

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
