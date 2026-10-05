# 부품별 상세 문서

이 폴더에는 로봇에 적용한 주요 부품의 사양, 연결 방식과 장착 시 주의사항을 정리한다.

| 문서 | 대상 부품 |
|---|---|
| [MEAN_WELL_LRS-150F-5.md](./MEAN_WELL_LRS-150F-5.md) | 5 V 서보 전원공급장치 |
| [INALWAYS_0717-2SCQ.md](./INALWAYS_0717-2SCQ.md) | AC 인렛·스위치·퓨즈 |
| [ATO_ATC_FUSE_BLOCK_6WAY.md](./ATO_ATC_FUSE_BLOCK_6WAY.md) | 서보 +5 V 퓨즈 분배 |
| [SMG_TYE-TB003.md](./SMG_TYE-TB003.md) | 공통 GND 버스바 |
| [MG90S.md](./MG90S.md) | MG90S 서보 |
| [MAIN_DISPLAY_5INCH.md](./MAIN_DISPLAY_5INCH.md) | 5인치 HDMI 메인 화면 |
| [ESP32_LCD.md](./ESP32_LCD.md) | ESP32와 3.5인치 얼굴 LCD |
| [USB_CAMERA.md](./USB_CAMERA.md) | USB 비전 카메라 |

전체 연결은 [wiring.md](../wiring.md), 전원 구성은 [power-budget.md](../power-budget.md), 서보 채널은 [MOTORS.md](../MOTORS.md)를 기준으로 한다.

## 기록 원칙

- 제조사 공식 사양, 판매 페이지 정보와 실물 측정값을 구분한다.
- 확인하지 않은 규격은 추정값으로 단정하지 않는다.
- 배선이나 채널이 바뀌면 상위 연결 문서와 함께 갱신한다.
