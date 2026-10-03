# Archived data — 2026-08-08

이 디렉터리는 2026-08-08 기준으로 보관한 과거 데이터 산출물이다.

## 상태

- **Archive / Legacy data**
- 현재 서비스 런타임의 기준 데이터 경로로 사용하지 않는다.
- 모델·데이터셋 변경 이력을 확인하거나 과거 결과를 재현할 때만 참고한다.
- 새 데이터 파일은 특별한 이유가 없으면 이 디렉터리에 추가하지 않는다.

## 보관 파일

- `merged_structure_b_v3.jsonl`
- `merged_structure_b_with_status_and_synthetic.jsonl`
- `single_menu_quantity_1_20_augmented.csv.gz`
- `single_menu_quantity_1_20_excluded.csv`
- `single_menu_quantity_1_20_statistics.json`
- `source_ice_americano_quantity_1.csv.gz.b64`

## 현재 데이터와의 구분

현재 개발에서 사용하는 데이터는 `data/`의 현행 파일과 각 모델/데이터셋 문서를 기준으로 확인한다.

서비스의 메뉴 정보는 데이터셋이 아니라 `config/menu_catalog.json`을 Single Source of Truth로 사용한다.

## 이동 기록

2026-08-10 저장소 정리 과정에서 목적이 모호했던

`experience/data_legacy_20260808/`

경로를 제거하고 이 위치로 옮겼다. 파일 내용은 변경하지 않았다.
