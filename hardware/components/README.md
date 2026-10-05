# 부품별 상세 문서

개별 부품의 공식 사양, 프로젝트 적용 방식, 구매 상태와 실물 시험 항목을 관리합니다.

상위 `hardware/` 폴더에는 전체 시스템 관점의 문서를 두고, 이 폴더에는 **부품 하나 또는 밀접하게 연결된 부품 묶음**의 상세 문서를 둡니다.

## 상세 문서 목록

| 문서 | 대상 부품 | 역할 |
|---|---|---|
| [`MEAN_WELL_LRS-150F-5.md`](./MEAN_WELL_LRS-150F-5.md) | MEAN WELL LRS-150F-5 | 공식 정격·보호·단자·토크·장착·디레이팅 |
| [`INALWAYS_0717-2SCQ.md`](./INALWAYS_0717-2SCQ.md) | Inalways 0717-2SCQ | C14 인렛·DPST 스위치·2중 퓨즈홀더·패널 가공 |
| [`ATO_ATC_FUSE_BLOCK_6WAY.md`](./ATO_ATC_FUSE_BLOCK_6WAY.md) | 6구 공통입력형 ATO/ATC 퓨즈박스 | 5 V 서보 플러스 분배·M5/M4 단자·외형 규격·실물 시험 |
| [`SMG_TYE-TB003.md`](./SMG_TYE-TB003.md) | SMG TYE-TB003 검정 6단자 버스바 | 5 V 공통 GND 분배·48 V/150 A 판매 사양·단자/장착 실측 항목 |
| [`MG90S.md`](./MG90S.md) | TowerPro 호환 MG90S | 서보 사양·장착 후보·실측 항목 |
| [`MAIN_DISPLAY_5INCH.md`](./MAIN_DISPLAY_5INCH.md) | 5인치 HDMI LCD, MXW-10W2U | Jetson 메인 화면·영상·전원 |
| [`ESP32_LCD.md`](./ESP32_LCD.md) | WeMos LOLIN D32, 3.5인치 ILI9488 | 얼굴 LCD·ESP32·SPI 연결 |
| [`USB_CAMERA.md`](./USB_CAMERA.md) | 1080 Full HD Auto Focus USB Camera | 어깨 고정 장착 위치·비전 입력 기준 |

## 상위 문서와의 관계

| 문서 | 저장하는 내용 |
|---|---|
| [`../components.yaml`](../components.yaml) | 부품 ID, 모델, 수량, 상태와 핵심 기계 판독값 |
| [`../PARTS.md`](../PARTS.md) | 사람이 빠르게 보는 보유·구매 목록과 수량 |
| [`../components.yaml`](../components.yaml) | 아직 확인되지 않은 규격, 구매·수령·시험 작업 |
| [`../wiring.md`](../wiring.md) | 실제 시스템에서 부품끼리 연결되는 방식 |
| [`../power-budget.md`](../power-budget.md) | 전원 용량·전류 예산·실측 결과 |
| [`../MOTORS.md`](../MOTORS.md) | 서보 위치와 PCA9685 채널 |
| [`../LRS-150F-5_CONNECTION_GUIDE.md`](../LRS-150F-5_CONNECTION_GUIDE.md) | MEAN WELL 공식 설치·안전·시험 기준 |
| [`../SERVO_POWER_CONNECTION_PLAN.md`](../SERVO_POWER_CONNECTION_PLAN.md) | 실제 결제할 전선·단자·분배 부품과 수량 |

## 새 부품을 기록할 때 반드시 함께 갱신할 파일

사용자가 새 부품의 사진·판매 링크·데이터시트를 제공하면 다음 순서로 처리합니다.

1. `components/<MANUFACTURER>_<MODEL>.md`에 공식 사양과 실물 확인표 작성
2. `components.yaml`에 고유 ID, 수량, 상태, 핵심 사양, `detail_doc` 연결
3. `PARTS.md`에 사람이 보는 요약·구매 수량·상태 반영
4. 확인되지 않은 값은 임의로 채우지 않고 `components.yaml`에 체크 항목으로 추가
5. 전원·신호 연결이 바뀌면 `wiring.md` 갱신
6. 전류·전압·출력 용량이 바뀌면 `power-budget.md` 갱신
7. 모터 위치·채널이 바뀌면 `MOTORS.md` 갱신
8. 전원 구매품이면 `SERVO_POWER_CONNECTION_PLAN.md`의 BOM과 단자표 갱신
9. 이 README와 상위 `hardware/README.md` 인덱스 갱신

## 기록 원칙

- 제조사 공식 문서, 실물 라벨, 판매 페이지를 구분해 기록합니다.
- 공식값과 프로젝트가 선택한 값이 다르면 각각 표시합니다.
- 확인되지 않은 퓨즈·나사·단자·핀 순서는 `미확인`로 남깁니다.
- 제품군 사양과 실제 변형 모델 사양을 혼동하지 않습니다.
- 구매 후 `planned → ordered → received → mounted → unit_tested → integrated` 순으로 `components.yaml` 상태를 갱신합니다.
- 같은 값이 여러 문서에 등장하면 상세 부품 문서와 `components.yaml`을 먼저 갱신한 뒤 요약 문서를 동기화합니다.