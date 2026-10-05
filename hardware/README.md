# Pumpkin Hardware

Pumpkin 고정형 무인매장 응대 로봇의 부품, 전력, 배선, 구매와 시험 기록을 관리합니다.

## 문서 역할과 우선순위

| 우선순위 | 문서 | 역할 |
|---:|---|---|
| 1 | [`components/`](./components/) | 부품별 공식 사양·프로젝트 적용·실물 확인표 |
| 2 | [`components.yaml`](./components.yaml) | 부품 ID·모델·수량·상태·핵심 사양의 기계 판독 기준 |
| 단자 구매 기준 | [`TERMINAL_PURCHASE_GUIDE.md`](./TERMINAL_PURCHASE_GUIDE.md) | 암 평단자·절연 포크·절연 링단자의 최종 규격, 쇼핑몰 검색어와 실제 사용 수량 |
| 3 | [`PARTS.md`](./PARTS.md) | 사람이 빠르게 보는 보유·구매 목록과 수량 |
| 4 | [`components.yaml`](./components.yaml) | 미확정 규격, 결제 전 확인, 수령·조립·시험 작업 |
| 5 | [`wiring.md`](./wiring.md) | 실제 전체 전원·신호 배선 |
| 얼굴 LCD 설치 기준 | [`JETSON_ESP32_LCD_SETUP.md`](./JETSON_ESP32_LCD_SETUP.md) | Jetson CH340 드라이버, brltty 충돌, 권한 설정과 실행 절차 |
| 6 | [`power-budget.md`](./power-budget.md) | 전원 용량, 서보 전류 예산과 실측값 |
| 7 | [`MOTORS.md`](./MOTORS.md) | 서보 위치·역할과 PCA9685 채널 |
| 공식 설치 기준 | [`LRS-150F-5_CONNECTION_GUIDE.md`](./LRS-150F-5_CONNECTION_GUIDE.md) | MEAN WELL 공식 사양·안전·장착·시험 절차 |
| 구매 실행 기준 | [`SERVO_POWER_CONNECTION_PLAN.md`](./SERVO_POWER_CONNECTION_PLAN.md) | 결제할 전선·분배 부품·단자·WAGO 수량 |

> [!IMPORTANT]
> LRS 공식 사양·설치 조건은 `LRS-150F-5_CONNECTION_GUIDE.md`와 `components/MEAN_WELL_LRS-150F-5.md`를 우선합니다. 압착단자 구매는 `TERMINAL_PURCHASE_GUIDE.md`를 우선하며, LRS에는 `1.25-3.5`·`2.5-3.5` 절연 포크단자를 사용하는 것으로 결정했습니다. PCA9685 채널은 `MOTORS.md`를 우선합니다.

## 부품별 상세 문서

| 부품 | 상세 문서 |
|---|---|
| MEAN WELL LRS-150F-5 | [`components/MEAN_WELL_LRS-150F-5.md`](./components/MEAN_WELL_LRS-150F-5.md) |
| Inalways 0717-2SCQ | [`components/INALWAYS_0717-2SCQ.md`](./components/INALWAYS_0717-2SCQ.md) |
| 6구 ATO/ATC 퓨즈박스 | [`components/ATO_ATC_FUSE_BLOCK_6WAY.md`](./components/ATO_ATC_FUSE_BLOCK_6WAY.md) |
| SMG TYE-TB003 GND 버스 | [`components/SMG_TYE-TB003.md`](./components/SMG_TYE-TB003.md) |
| 압착단자 구매표 | [`TERMINAL_PURCHASE_GUIDE.md`](./TERMINAL_PURCHASE_GUIDE.md) |
| MG90S | [`components/MG90S.md`](./components/MG90S.md) |
| 5인치 HDMI LCD | [`components/MAIN_DISPLAY_5INCH.md`](./components/MAIN_DISPLAY_5INCH.md) |
| ESP32·3.5인치 얼굴 LCD | [`components/ESP32_LCD.md`](./components/ESP32_LCD.md) |

## Jetson–ESP32 얼굴 LCD 연동 상태

2026-08-06 실제 장비에서 다음 전체 경로의 동작을 확인했습니다.

```text
Jetson Orin Nano
  → USB Serial 115200 baud
LOLIN D32 / ESP32
  → TFT_eSPI + SPI
3.5-inch ILI9488 LCD
```

Jetson 제어 코드는 실제 시험을 완료한 뒤 `feat/jetson-lcd-face-controller`에서 `main`으로 병합했습니다.

```text
robot_face/jetson/face_controller.py
robot_face/jetson/README.md
robot_face/esp32_lcd/esp32_lcd_face.ino
```

평소 실행은 다음과 같습니다.

```bash
cd ~/pumpkin
git switch main
git pull
source .venv/bin/activate
python3 robot_face/jetson/face_controller.py --demo
```

현재 Jetson 환경은 R36.5.0, 커널 `5.15.185-tegra`이며, LOLIN D32의 CH340 USB Serial 칩은 USB ID `1a86:7523`으로 확인했습니다. 해당 NVIDIA 커널에는 `CONFIG_USB_SERIAL_CH341`이 비활성화되어 있어 동일 버전 커널 소스로 `ch341.ko`를 직접 빌드해 설치했습니다.

팀원이 반드시 알아야 할 사항:

- `lsusb`에 CH340이 보여도 `/dev/ttyUSB0`이 없다면 CH341 커널 모듈을 확인합니다.
- Ubuntu의 `brltty`가 CH340을 점자 장치로 잘못 인식하면 `/dev/ttyUSB0`이 생성 직후 사라질 수 있습니다.
- `Permission denied`가 발생하면 사용자가 `dialout` 그룹에 포함되어 있는지 확인합니다.
- 현재 `ch341.ko`는 `5.15.185-tegra` 전용이므로 커널 업데이트 후에는 새 커널용으로 다시 빌드해야 합니다.
- Arduino Serial Monitor와 Jetson Python 프로그램은 같은 Serial 포트를 동시에 열 수 없습니다.
- 커널 종속 바이너리인 `.ko` 파일은 저장소에 커밋하지 않습니다.

설치 확인, 문제 진단, 재부팅 후 영구 설정과 커널 업데이트 주의사항은 [`JETSON_ESP32_LCD_SETUP.md`](./JETSON_ESP32_LCD_SETUP.md)를 기준으로 합니다.

## 새 부품 기록 표준 작업

사용자가 “이 부품 기록해줘”라고 요청하면 다음 파일을 한 번에 확인하고 갱신합니다.

1. `hardware/components/<MANUFACTURER>_<MODEL>.md`
2. `hardware/components.yaml`
3. `hardware/PARTS.md`
4. `hardware/components.yaml`
5. 연결이 바뀌면 `hardware/wiring.md`
6. 전력 조건이 바뀌면 `hardware/power-budget.md`
7. 모터이면 `hardware/MOTORS.md`
8. 전원 구매품이면 `hardware/SERVO_POWER_CONNECTION_PLAN.md`
9. 단자 규격·수량이 바뀌면 `hardware/TERMINAL_PURCHASE_GUIDE.md`
10. `hardware/components/README.md`와 이 README의 인덱스

### 기록 원칙

- 공식 문서로 확인된 값은 `확정`으로 기록합니다.
- 판매 페이지에만 있는 값은 출처를 표시합니다.
- 실물 확인이 필요한 나사·퓨즈·단자·핀 순서는 임의로 확정하지 않고 `components.yaml`에 추가합니다.
- 구매 후 상태는 `planned → ordered → received → mounted → unit_tested → integrated` 순으로 갱신합니다.
- 동일 값이 여러 문서에 있으면 상세 component 문서와 `components.yaml`을 먼저 고친 뒤 요약 문서를 동기화합니다.

## 최종 로봇 조건

- 이동하지 않는 고정형 로봇
- 팔 1개, 목 2축
- 이동용 바퀴 모터와 모터 드라이버 없음
- 최종 장착 서보 9개

| 구동부 | 구성 |
|---|---|
| 팔 | DS3218 ×2, MG996R ×2, MG90S ×3 |
| 목 | MG996R ×2 |

MG995 2개와 SG90 1개는 예비품으로 보관합니다.

## 최종 서보 전원

최종 서보 전원은 **MEAN WELL LRS-150F-5, 5 V / 22 A / 110 W**입니다.

| 전원 | 용도 | 상태 |
|---|---|---|
| LRS-75-5, 5 V / 14 A / 70 W | 단품·부분 구동·예비 | 보유 |
| LRS-150F-5, 5 V / 22 A / 110 W | 서보 9개 최종 전원 | 구매 예정 |
| LRS-200-5, 5 V / 40 A | 사용하지 않음 | 현재 구성에는 과도함 |

LRS-75-5와 LRS-150F-5의 출력을 병렬 연결하지 않습니다.

## 6구 ATO/ATC 퓨즈박스 규격

서보 전원 플러스 분배에는 **6구 공통입력형 ATO/ATC 퓨즈박스**를 사용합니다. 아래 값은 제공된 판매 이미지 기준이며, 실물 수령 후 다시 측정합니다.

| 항목 | 규격 |
|---|---|
| 외형 | 약 85 × 70 × 35 mm |
| 최대 전압 | 32 V DC |
| 전체 최대 전류 | 100 A |
| 회로별 최대 전류 | 30 A |
| 공통 입력 | M5 스터드 표시 |
| 분기 출력 | M4 나사 표시 |
| 적용 퓨즈 | ATO/ATC 블레이드 퓨즈 |
| 커버 | 투명 커버 포함 |

동봉 구성품은 5 A 퓨즈 2개, 10 A 2개, 15 A 4개, 20 A 4개, 고정 나사 4개, 회로명 스티커 40장, 절연 링단자 10개로 표시되어 있습니다. 최종 퓨즈 정격은 동봉품에 맞추지 않고 분기별 피크전류와 배선 허용전류를 실측한 뒤 선정합니다.

제공된 이미지 중 `50 × 120 × 52 mm`로 표시된 제품은 12구형으로 보이며, 현재 선택한 6구형과 다른 제품입니다.

## SMG TYE-TB003 GND 분배 블록 규격

서보와 제어보드의 공통 GND 분배에는 **SMG TYE-TB003 검정 6단자 버스바**를 사용합니다. 이 부품은 퓨즈가 없는 공통 전위 분배 블록입니다.

| 항목 | 판매 페이지 기준 규격 |
|---|---|
| 모델 | SMG TYE-TB003, 검정 6단자형 |
| 외형 | 약 121 × 42 × 20 mm |
| 최대 전압 | 48 V DC |
| 연속 전류 | 150 A |
| 무게 | 약 80 g |
| 재질 표시 | ABS, 아연 합금, 황동 |
| 커버 | 투명 절연·방진 커버 포함 |
| 구성품 | 분배 블록 1개, 고정 나사 2개 |

프로젝트에서는 `LRS-150F-5 -V → 검정 2.5SQ/AWG12 → TYE-TB003`으로 연결하고, 목·팔·MG90S 서보 분기와 PCA9685·ESP32의 GND를 각각 소형 단자에 연결합니다. 판매 페이지에는 대형 스터드와 소형 나사의 정확한 규격 및 체결 토크가 없으므로 실물 또는 데이터시트 확인 전에는 M5/M6·M4 링단자를 확정하지 않습니다.

## 최종 전원 분배 구조

```text
외부 220 V AC
    │
    ▼
접지형·과부하 차단형 멀티탭
    ├── Jetson 전용 어댑터
    ├── 5인치 LCD 전용 어댑터
    ├── USB 허브 전용 어댑터
    └── C13 케이블
             │
             ▼
       0717-2SCQ
             │
             ▼
       LRS-150F-5
          ├── +V → 2.5SQ → 6구 ATO/ATC 퓨즈박스
          │                  ├── F1 1.0SQ → 목 MG996R ×2
          │                  ├── F2 1.5SQ → DS3218 ×2
          │                  ├── F3 1.0SQ → 팔 MG996R ×2
          │                  └── F4 1.0SQ → MG90S ×3
          └── -V → 2.5SQ → SMG TYE-TB003 GND 버스
                             ├── G1~G4 서보 GND 분기
                             ├── G5 PCA9685 GND
                             └── G6 ESP32 GND
```

## 핵심 공식 기준

- LRS-150F-5: `5 V / 22 A / 110 W`
- AC 입력: `85~264 V AC`, 풀레인지
- LRS 단자: M3.5, `8~10 kgf·cm`
- LRS 전선 마감: AC 0.75SQ는 `1.25-3.5`, DC 2.5SQ는 `2.5-3.5` 절연 포크단자 사용
- AC 내부선: VCTF 0.75SQ×3C
- DC 메인선: 2.5SQ/AWG12
- 목·팔 MG996R·MG90S 분기: 1.0SQ/AWG16
- DS3218 분기: 1.5SQ/AWG14, 실측이 16 A를 넘으면 2.5SQ 또는 분기 재검토
- 퓨즈박스 판매 이미지 기준: `85 × 70 × 35 mm`, 공통 M5, 분기 M4
- TYE-TB003 판매 페이지 기준: `121 × 42 × 20 mm`, 최대 48 V DC, 연속 150 A
- 표준 수평 장착, 통풍구 차단 금지
- 열원과 10~15 cm 이격 또는 별도 환기 설계
- FG 보호접지 필수

## 현재 다음 작업

1. [`TERMINAL_PURCHASE_GUIDE.md`](./TERMINAL_PURCHASE_GUIDE.md)의 최종 단자 규격과 쇼핑몰 검색어 확인
2. LRS-150F-5, 0717-2SCQ, 퓨즈박스, SMG TYE-TB003, 전선·단자 구매
3. 퓨즈박스 수령 후 6구 공통입력형 여부, 85 × 70 × 35 mm 외형, M5/M4 단자와 고정홀 실측
4. TYE-TB003 수령 후 대형 스터드·소형 나사·장착홀·커버 포함 높이와 전체 단자 연속성 확인
5. AC 배선 검토와 무부하 약 5.0 V 시험
6. 서보 단품 → 분기 → 전체 서비스 동작 순서로 전류·전압·발열 측정
7. 분기별 최종 퓨즈 정격 확정
8. 실측값을 `components.yaml`, `PARTS.md`, `components.yaml`, `wiring.md`, `power-budget.md`에 동기화

## 변경 기록

| 날짜 | 변경 내용 |
|---|---|
| 2026-08-26 | CH7 장착 서보를 MG995에서 `SERVO_MG996R_04`로 교체. 최종 팔 구성을 DS3218×2 + MG996R×2 + MG90S×3으로 변경하고 F3/G3 분기를 MG996R×2로 통일. |
