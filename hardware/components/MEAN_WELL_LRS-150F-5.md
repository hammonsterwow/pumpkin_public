# MEAN WELL LRS-150F-5 전원공급장치

Pumpkin 로봇의 목·팔 서보 9개에 전원을 공급하는 5 V 전원공급장치입니다.

> [!DANGER]
> 입력 단자에는 220 V AC 상용전원이 직접 연결됩니다. 배선과 점검은 플러그를 분리한 상태에서 진행하고, 보호접지와 절연 상태를 확인합니다.

## 현재 프로젝트 적용

| 항목 | 내용 |
|---|---|
| 모델 | MEAN WELL `LRS-150F-5` |
| 수량 | 1개 |
| 출력 | 5 V DC / 22 A / 110 W |
| 전원 대상 | MG996R ×5, DS3218 ×1, MG90S ×3 |
| 비전원 대상 | Jetson, 메인 디스플레이, ESP32 로직 전원 |
| DC 분배 | +V → 6구 퓨즈박스, -V → GND 버스 |

서보 구성은 [`../MOTORS.md`](../MOTORS.md), 분기별 전류와 퓨즈 기준은 [`../power-budget.md`](../power-budget.md)을 따릅니다.

## 주요 공식 사양

| 항목 | 공식 값 |
|---|---:|
| AC 입력 범위 | 85~264 V AC, 47~63 Hz |
| 230 V AC 입력전류 | 1.7 A typ. |
| 230 V 냉간 돌입전류 | 60 A typ. |
| DC 출력 | 5 V, 0~22 A |
| 정격 출력 | 110 W |
| 출력 조정 범위 | 4.5~5.5 V |
| 출력 허용오차 | ±2.0% |
| 효율 | 85% typ. |
| 냉각 방식 | 자연 공랭 |
| 크기 | 159 × 97 × 30 mm |
| 무게 | 약 0.42 kg |

5 V 모델은 제품군 이름의 150 W와 달리 정격 출력이 110 W이므로 시스템 계산에는 5 V / 22 A / 110 W를 사용합니다.

## 보호 기능

| 보호 기능 | 동작 |
|---|---|
| 단락 | 과부하 보호와 함께 동작 |
| 과부하 | 정격 출력의 110~140%, hiccup mode |
| 과전압 | 5.75~6.75 V에서 출력 정지 |
| 과온도 | 출력 정지 후 냉각·원인 제거 필요 |

내장 보호 기능은 분기 퓨즈, 올바른 배선 굵기, 커넥터 정격과 기계적 스톨 방지를 대신하지 않습니다.

## 단자

| 번호 | 표기 | 역할 |
|---:|---|---|
| 1 | AC/L | AC Live |
| 2 | AC/N | AC Neutral |
| 3 | FG | 보호접지 |
| 4, 5 | -V | 5 V DC 마이너스 |
| 6, 7 | +V | 5 V DC 플러스 |

```text
0717-2SCQ LOAD L ── LRS AC/L
0717-2SCQ LOAD N ── LRS AC/N
0717-2SCQ PE     ── LRS FG

LRS +V ── 6구 ATO/ATC 퓨즈박스 ── 서보 +5 V
LRS -V ── GND 버스 ── 서보 GND / PCA9685 GND / Jetson GND
```

FG는 보호접지이고 -V는 DC 출력 기준점이므로 임의로 같은 단자로 취급하지 않습니다.

## 설치·운용 원칙

- AC 입력과 DC/신호 배선을 물리적으로 분리합니다.
- FG를 건물 보호접지에 연결합니다.
- 통풍구를 막지 않고 전원공급장치를 기구물에 단단히 고정합니다.
- 여러 서보선을 LRS 단자에 직접 겹쳐 체결하지 않고 퓨즈박스와 GND 버스를 통해 분배합니다.
- 출력전압, 동작 중 전압강하, 분기 전류와 단자 발열을 실제 로봇 동작에서 확인합니다.
- 전원 투입·차단은 [`../SERVO_POWER_ON_OFF_MANUAL.md`](../SERVO_POWER_ON_OFF_MANUAL.md)을 따릅니다.

## 관련 문서

- [`../LRS-150F-5_CONNECTION_GUIDE.md`](../LRS-150F-5_CONNECTION_GUIDE.md): 연결 및 안전 절차
- [`INALWAYS_0717-2SCQ.md`](./INALWAYS_0717-2SCQ.md): AC 인렛
- [`ATO_ATC_FUSE_BLOCK_6WAY.md`](./ATO_ATC_FUSE_BLOCK_6WAY.md): DC 분기 퓨즈
- [`../power-budget.md`](../power-budget.md): 전원 용량
- [`../wiring.md`](../wiring.md): 전체 배선

## 근거 자료

- MEAN WELL LRS-150F 제품 사양서
- MEAN WELL Enclosed Type 설치 매뉴얼
