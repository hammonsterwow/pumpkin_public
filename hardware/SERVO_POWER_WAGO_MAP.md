# Servo Power · GND Bus · WAGO 최종 연결표

Pumpkin 로봇의 서보 9개를 `LRS-150F-5`, 6구 ATO/ATC 퓨즈박스, SMG TYE-TB003 GND 버스, WAGO 221 커넥터와 연결할 때 사용하는 **실제 조립 기준표**입니다.

> 이 문서는 서보 전원 분배와 WAGO/GND 연결에 대해서는 `wiring.md`의 상세 보조 기준으로 사용합니다. 퓨즈 번호와 서보 ID/PCA9685 채널은 `MOTORS.md`와 동일하게 유지합니다.

## 결론

- **서보 9개의 GND는 모두 LRS-150F-5의 `-V`와 연결된 GND 버스로 돌아가야 합니다.**
- 다만 서보 GND 9가닥을 GND 버스에 하나씩 직접 꽂지 않습니다.
- 같은 퓨즈 그룹의 서보 GND를 **GND용 WAGO 하나에 먼저 묶고**, WAGO에서 굵은 검정 분기선 1가닥만 GND 버스로 연결합니다.
- 서보의 빨간 `+5 V` 선도 퓨즈박스에서 각 서보로 바로 여러 가닥을 뽑지 않고, **퓨즈 출력 → +5 V용 WAGO → 그룹 내 서보들** 순서로 분배합니다.
- PCA9685에서는 각 서보의 **Signal만** 연결합니다. 서보의 고전류 +5 V/GND를 PCA9685 헤더나 PCB 패턴으로 흘리지 않습니다.

```text
LRS +V
  ↓
6구 퓨즈박스
  ├─ F1 5 A  → + WAGO → 목 MG996R ×2 빨간선
  ├─ F2 10 A → + WAGO → DS3218 ×2 빨간선
  ├─ F3 5 A  → + WAGO → MG996R ×2 빨간선
  └─ F4 5 A  → + WAGO → MG90S ×3 빨간선

LRS -V
  ↓
GND 버스
  ├─ G1 → GND WAGO → 목 MG996R ×2 GND
  ├─ G2 → GND WAGO → DS3218 ×2 GND
  ├─ G3 → GND WAGO → MG996R ×2 GND
  ├─ G4 → GND WAGO → MG90S ×3 GND
  ├─ G5 → PCA9685 GND
  └─ G6 → ESP32 GND

PCA9685 CHx Signal → 각 서보 노랑/주황 신호선
```

## GND 버스 최종 배정

SMG TYE-TB003의 메인 입력에는 `LRS-150F-5 -V`를 검정 2.5SQ/AWG12로 연결합니다. 분기 단자는 아래처럼 사용합니다.

| GND 버스 ID | 연결 대상 | 분기 전선 | 다음 연결 |
|---|---|---|---|
| MAIN | `LRS-150F-5 -V` | 검정 2.5SQ/AWG12 | GND 버스 공통 입력 |
| G1 | 목 서보 그룹 | 검정 1.0SQ/AWG16 | `WAGO_G_F1_NECK` |
| G2 | DS3218 그룹 | 검정 1.5SQ/AWG14 | `WAGO_G_F2_DS` |
| G3 | MG996R 그룹 | 검정 1.0SQ/AWG16 | `WAGO_G_F3_MG` |
| G4 | MG90S 그룹 | 검정 1.0SQ/AWG16 | `WAGO_G_F4_MG90S` |
| G5 | PCA9685 로직 기준 GND | 검정 0.5~0.75SQ | PCA9685 `GND` |
| G6 | ESP32 공통 GND | 검정 0.5~0.75SQ | LOLIN D32 `GND` |

G1~G6 번호는 **실물 버스바에 직접 라벨을 붙여** 문서와 동일하게 관리합니다. 제품 방향만 보고 좌/우 번호를 추정하지 않습니다.

## WAGO 최종 배정

현재 구매 계획의 `WAGO 221-413 ×3`, `WAGO 221-415 ×5`를 모두 사용하면 추가 구매 없이 4개 +5 V 그룹과 4개 GND 그룹을 만들 수 있습니다.

WAGO 내부의 모든 포트는 서로 공통 연결되어 있으므로 별도의 입력/출력 방향은 없습니다. 아래 표의 `포트 1` 등은 조립 시 식별을 위한 권장 배치입니다.

### +5 V용 WAGO 4개

| WAGO ID | 모델 | 포트 연결 | 퓨즈 |
|---|---|---|---|
| `WAGO_P_F1_NECK` | 221-413 | ① F1 출력 1.0SQ 빨강, ② `SERVO_MG996R_01` 빨강, ③ `SERVO_MG996R_02` 빨강 | F1 / 5 A |
| `WAGO_P_F2_DS` | 221-413 | ① F2 출력 1.5SQ 빨강, ② `SERVO_DS3218_01` 빨강, ③ `SERVO_DS3218_02` 빨강 | F2 / 10 A |
| `WAGO_P_F3_MG` | 221-413 | ① F3 출력 1.0SQ 빨강, ② `SERVO_MG996R_03` 빨강, ③ `SERVO_MG996R_04` 빨강 | F3 / 5 A |
| `WAGO_P_F4_MG90S` | 221-415 | ① F4 출력 1.0SQ 빨강, ② `SERVO_MG90S_01` 빨강, ③ `SERVO_MG90S_02` 빨강, ④ `SERVO_MG90S_03` 빨강, ⑤ 비움 | F4 / 5 A |

### GND용 WAGO 4개

| WAGO ID | 모델 | 포트 연결 |
|---|---|---|
| `WAGO_G_F1_NECK` | 221-415 | ① GND 버스 G1의 1.0SQ 검정, ② `SERVO_MG996R_01` GND, ③ `SERVO_MG996R_02` GND, ④~⑤ 비움 |
| `WAGO_G_F2_DS` | 221-415 | ① GND 버스 G2의 1.5SQ 검정, ② `SERVO_DS3218_01` GND, ③ `SERVO_DS3218_02` GND, ④~⑤ 비움 |
| `WAGO_G_F3_MG` | 221-415 | ① GND 버스 G3의 1.0SQ 검정, ② `SERVO_MG996R_03` GND, ③ `SERVO_MG996R_04` GND, ④~⑤ 비움 |
| `WAGO_G_F4_MG90S` | 221-415 | ① GND 버스 G4의 1.0SQ 검정, ② `SERVO_MG90S_01` GND, ③ `SERVO_MG90S_02` GND, ④ `SERVO_MG90S_03` GND, ⑤ 비움 |

따라서 실제 사용 수량은 다음과 같습니다.

```text
221-413 ×3  → F1/F2/F3 +5 V 분배
221-415 ×1  → F4 +5 V 분배
221-415 ×4  → F1/F2/F3/F4 GND 분배
─────────────────────────────
총 221-413 ×3 + 221-415 ×5 = WAGO 8개
```

## 서보별 최종 3선 연결

| 서보 ID | +5 V 빨간선 | GND 갈색/검정선 | Signal 노랑/주황선 |
|---|---|---|---|
| `SERVO_MG996R_01` | `WAGO_P_F1_NECK` | `WAGO_G_F1_NECK` | PCA9685 CH0 |
| `SERVO_MG996R_02` | `WAGO_P_F1_NECK` | `WAGO_G_F1_NECK` | PCA9685 CH1 |
| `SERVO_DS3218_01` | `WAGO_P_F2_DS` | `WAGO_G_F2_DS` | PCA9685 CH4 |
| `SERVO_DS3218_02` | `WAGO_P_F2_DS` | `WAGO_G_F2_DS` | PCA9685 CH5 |
| `SERVO_MG996R_03` | `WAGO_P_F3_MG` | `WAGO_G_F3_MG` | PCA9685 CH6 |
| `SERVO_MG996R_04` | `WAGO_P_F3_MG` | `WAGO_G_F3_MG` | PCA9685 CH7 |
| `SERVO_MG90S_01` | `WAGO_P_F4_MG90S` | `WAGO_G_F4_MG90S` | PCA9685 CH8 |
| `SERVO_MG90S_02` | `WAGO_P_F4_MG90S` | `WAGO_G_F4_MG90S` | PCA9685 CH9 |
| `SERVO_MG90S_03` | `WAGO_P_F4_MG90S` | `WAGO_G_F4_MG90S` | PCA9685 CH10 |

## Fritzing에서 현재 그림 수정 순서

현재 배선도를 수정할 때는 아래 순서로 정리합니다.

1. **PCA9685 → 서보로 연결된 빨간 전원선과 갈색/검정 GND선을 제거**합니다.
2. PCA9685에서 각 서보로는 해당 채널의 **Signal 1가닥만** 남깁니다.
3. 퓨즈박스 F1~F4 출력선을 서보로 직접 여러 갈래 연결하지 않고 각각 해당 `WAGO_P_*` 한 곳으로 연결합니다.
4. 각 `WAGO_P_*`에서 해당 그룹 서보의 빨간선으로 분기합니다.
5. GND 버스 G1~G4에서 각각 해당 `WAGO_G_*` 한 곳으로 검정 분기선을 연결합니다.
6. 각 `WAGO_G_*`에서 해당 그룹 서보의 갈색/검정 GND선으로 분기합니다.
7. GND 버스 G5는 PCA9685 GND, G6는 ESP32 GND에 직접 연결합니다.
8. F5·F6은 퓨즈 미장착 상태로 비워 둡니다.

## 연결 원칙과 주의

- +5 V용 WAGO와 GND용 WAGO는 **절대 같은 커넥터를 공유하지 않습니다.**
- WAGO의 남는 포트는 아무것도 연결하지 않고 비워 둡니다.
- WAGO 221-413은 3-conductor, 221-415는 5-conductor 제품이며 WAGO 공식 사양상 최대 4 mm² 전선을 지원하므로 프로젝트의 1.0SQ/1.5SQ 분기선 범위에 들어갑니다.
- 서보 연장 하네스의 실제 색상과 핀 순서는 제조사/제품에 따라 다를 수 있으므로 전원 투입 전 실물 핀 순서를 확인합니다.
- 원래 서보 케이블은 자르지 않고 JR/Futaba 연장선을 가공하여 전원·GND·Signal을 분리합니다.
- PCA9685 `VCC`는 ESP32 3.3 V 로직 전원, PCA9685 `GND`는 GND 버스와 공통으로 연결합니다.
- PCA9685 `V+`는 최종 서보 9개 고전류 전원 분배 경로로 사용하지 않습니다.
- 전원 배선 작업은 AC 플러그와 LRS 전원을 완전히 분리한 상태에서 수행하고, 최초 전원 인가 전 +V/-V 단락과 극성을 멀티미터로 확인합니다.

## 관련 문서

- `hardware/wiring.md`: 전체 전원·신호 배선
- `hardware/MOTORS.md`: 서보 ID·PCA9685 채널·퓨즈 배정
- `hardware/power-budget.md`: 퓨즈값과 전류 예산
- `hardware/components/ATO_ATC_FUSE_BLOCK_6WAY.md`: 6구 퓨즈박스
- `hardware/components/SMG_TYE-TB003.md`: GND 버스

## 변경 기록

| 날짜 | 내용 |
|---|---|
| 2026-08-26 | PCA9685 CH7의 `SERVO_MG995_01`(MG995)을 `SERVO_MG996R_04`(MG996R)로 교체. F3 그룹을 MG996R ×2 구성으로 갱신. |
| 2026-08-17 | 실제 Fritzing 조립 기준으로 서보 9개 GND를 4개 그룹 WAGO를 통해 GND 버스로 귀환하도록 확정. +5 V WAGO 4개와 GND WAGO 4개의 ID·포트·서보 배정을 확정하고, 기존 구매 계획 `221-413 ×3 + 221-415 ×5`를 모두 사용하는 배치로 기록. |
