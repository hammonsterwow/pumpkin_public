# KIPS 2026 NLU 실험 — 3인 분담

## 사용할 노트북

| 파일 | 담당 실험 | 실행 횟수 |
|---|---|---:|
| `01_M0_independent_heads.ipynb` | M0: KoELECTRA-small + Independent Item Heads | seeds 42/43/44 = 3회 |
| `02_M1_item_query.ipynb` | M1: KoELECTRA-small + Item Query Decoder | seeds 42/43/44 = 3회 |
| `03_M2_improved_item_query.ipynb` | M2: Item Query + Diff LR + Oversampling + Weighted Loss | seeds 42/43/44 = 3회 |
| `04_ablation.ipynb` | A0→A3, 선택적 R-Drop | 메인 실험 후 진행 |

## 3명 분담 예시

- 1명: `01_M0_independent_heads.ipynb`
- 1명: `02_M1_item_query.ipynb`
- 1명: `03_M2_improved_item_query.ipynb`
- 메인 9회 결과가 모인 뒤 `04_ablation.ipynb`는 한 명이 맡거나 순차 분담

각 메인 노트북은 자기 모델만 고정해서 실행하므로 다른 모델 설정을 건드릴 필요가 없습니다.

## 공통 조건

모든 사람이 아래 조건을 바꾸지 않습니다.

- Encoder: `monologg/koelectra-small-v3-discriminator`
- 데이터: `data/structure_b_train_valid.jsonl`, `data/structure_b_test.jsonl`
- seeds: 42, 43, 44
- max length: 96
- max items: 3
- 동일 `config.py`, `data_utils.py`, `models.py`, `train_eval.py`

실험 시작 전에 모두 같은 `main` commit을 clone해야 합니다.

## 결과 제출

각 담당자는 노트북 마지막 셀에서 생성된 ZIP 하나를 공유합니다.

- M0 담당: `kips_M0_results.zip`
- M1 담당: `kips_M1_results.zip`
- M2 담당: `kips_M2_results.zip`
- Ablation 담당: `kips_ablation_results.zip`

각 ZIP 내부의 `runs/<experiment>_seed<seed>/`에는 다음이 저장됩니다.

- `best_model.pt`
- `history.csv`
- `test_predictions.csv`
- `test_errors.csv`
- `result.json`

## Ablation 진행 순서

메인 M0/M1/M2가 끝난 후 진행합니다.

1. `04_ablation.ipynb`에서 A0~A3를 seed 42 하나로 screening
2. 결과 차이가 의미 있으면 `RUN_THREE_SEEDS=True`로 바꿔 42/43/44 실행
3. R-Drop은 필요할 때만 `RUN_RDROP=True`

A0는 M1과 동일하고 A3는 M2와 동일한 설정입니다. 새 Colab 세션에서는 캐시가 없으면 다시 학습하지만, 분석 단계에서는 메인 M1/M2 결과를 대응 값으로 사용할 수 있습니다.

## 기존 master notebook

`kips_item_query_experiments_colab.ipynb`는 M0/M1/M2와 ablation을 한 Colab에서 모두 실행하고 싶을 때만 사용합니다. 3명이 병렬 실험할 때는 위의 `01`~`04` 분리 노트북을 사용하세요.
