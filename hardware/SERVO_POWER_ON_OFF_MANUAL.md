# Pumpkin 서보 전원 ON/OFF 안전 매뉴얼

이 문서는 Pumpkin 로봇의 `LRS-150F-5 + PCA9685 + 서보 9개` 전원을 켜고 끌 때의 **운용 순서와 Jetson 안전 제어 절차**를 정리합니다.

현재 하드웨어에서는 Jetson이 220 V 인렛 스위치를 직접 제어하지 않습니다. 따라서:

- **Jetson 프로그램:** PCA9685 `OE(Output Enable)` 제어, PCA 초기화, HOME PWM 사전 설정
- **사람:** Inalways 0717-2SCQ 인렛 스위치로 LRS/서보 5 V 전원 ON/OFF

를 각각 담당합니다.

> [!DANGER]
> 이 절차는 비정상 전압 원인을 해결하는 보호회로가 아닙니다. F4에서 관측된 비정상 과전압 원인을 찾기 전에는 전체 서보를 다시 연결해 반복 시험하지 않습니다.

---

## 1. 왜 인렛만 바로 ON/OFF하지 않는가

현재 서보 전원은 다음 구조입니다.

```text
220 V AC
  ↓
0717-2SCQ 인렛
  ↓
LRS-150F-5 5 V / 22 A
  ↓
6구 퓨즈박스
  ├─ F1 → 목 MG996R ×2
  ├─ F2 → DS3218 ×2
  ├─ F3 → 팔 MG996R ×2
  └─ F4 → MG90S ×3
```

PCA9685는 서보 고전류 전원을 공급하지 않고 각 서보의 PWM Signal만 생성합니다.

인렛을 바로 끄면 서보의 holding torque가 사라집니다. 팔이 중력 때문에 떨어지거나 관절이 역회전하면 모터가 기계적으로 back-drive될 수 있습니다. 따라서 전원을 끌 때 팔을 먼저 안정된 자세로 두고 **물리적으로 지지**해야 합니다.

또한 로직 전원과 서보 전원이 서로 다른 속도로 올라가거나 내려가면 부팅/종료 순간 잘못된 PWM 상태가 서보에 전달될 수 있으므로 PCA9685 `OE`를 사용합니다.

---

## 2. 추가해야 하는 OE 배선

### 2.1 1차 적용: 현재 바로 사용할 배선

```text
Jetson Orin Nano 40-pin header
BOARD pin 12 (GPIO output)
          │
          └────────────→ PCA9685 OE

Jetson GND ────────────→ PCA9685 GND / 공통 GND
```

프로그램 기본값은 `BOARD pin 12`입니다.

다른 핀을 사용해야 하면 실행 전에 다음 환경변수로 바꿀 수 있습니다.

```bash
export PUMPKIN_PCA_OE_BOARD_PIN=12
```

### 2.2 OE 동작

```text
OE LOW  → PCA9685 PWM 출력 허용
OE HIGH → PCA9685 PWM 출력 강제 차단
```

### 2.3 중요한 한계

일반적인 PCA9685 breakout의 OE는 기본적으로 LOW 쪽으로 유지되는 제품이 많습니다. 따라서 **Jetson이 완전히 꺼져 있거나 부팅 중인 동안까지 포함한 진짜 fail-safe**를 만들려면 최종 하드웨어에서는 OE가 기본 HIGH가 되도록 별도의 fail-safe 회로를 추가해야 합니다.

권장 최종 방향은:

```text
Jetson GPIO
   ↓
트랜지스터/버퍼 회로
   ↓
PCA9685 OE

Jetson이 꺼짐/재부팅/선 빠짐
   ↓
OE가 자동 HIGH
   ↓
PWM 비활성
```

입니다.

단순 소프트웨어만으로는 Jetson이 꺼져 있는 시간의 OE 상태를 보장할 수 없습니다.

---

## 3. Jetson에 추가된 프로그램

### Python 본체

```text
scripts/pca9685/servo_power_sequence.py
```

### 간단 실행 스크립트

```text
scripts/servo_power_on.sh
scripts/servo_power_off.sh
```

프로그램은 현재 저장소에서 검증된 HOME 값을 사용합니다.

```text
CH0  = 60   head tilt center
CH1  = 90   head pan center
CH4  = 90
CH5  = 90
CH6  = 90
CH7  = 1
CH8  = 1
CH9  = 140
CH10 = 179
```

팔 CH4~CH10은 기존 물리 테스트와 동일하게 `1000~2000 us` pulse width range를 사용합니다.

---

# 4. 정상 POWER ON 절차

## 절대로 먼저 인렛을 켜지 않는다

시작 상태:

```text
Jetson        ON 또는 부팅 완료
PCA9685 logic ON
서보/LRS 인렛 OFF
팔            물리적으로 지지
```

Jetson 터미널에서:

```bash
cd ~/pumpkin
bash scripts/servo_power_on.sh
```

프로그램 내부 순서는 다음과 같습니다.

```text
[1] PCA9685 OE HIGH
    → PWM 차단

[2] PCA9685 I2C 초기화

[3] HOME PWM register 미리 기록
    → OE가 HIGH이므로 아직 서보는 움직이지 않음

[4] 사용자가 READY 입력

[5] 사용자가 인렛 ON
    → LRS/서보 5 V 공급
    → 아직 PWM 차단 상태

[6] 사용자가 ON 입력

[7] 약 1초 안정화

[8] OE LOW
    → PWM 활성화
    → 서보가 HOME 목표를 받음
```

### 실제 화면에서 할 일

프로그램에 다음이 표시되면:

```text
If the arm is supported and the inlet is still OFF, type READY:
```

팔을 지지하고 인렛이 OFF인지 확인한 뒤:

```text
READY
```

입력합니다.

그 다음 프로그램이 인렛을 켜라고 하면 **0717-2SCQ 인렛을 ON**합니다.

그 뒤:

```text
ON
```

을 입력합니다.

`[OK] Servo PWM enabled`가 나온 후에만 실제 로봇 실행 프로그램을 시작합니다.

---

# 5. 정상 POWER OFF 절차

종료는 ON보다 중요합니다.

## 5.1 로봇을 먼저 안정화

현재 진행 중인 팔 동작을 끝냅니다.

기존 팔 제어는 각 제스처가 끝난 뒤 HOME/attention 자세로 돌아오도록 되어 있으므로 **팔이 완전히 HOME으로 돌아온 것을 눈으로 확인**합니다.

그 다음 새 동작이 들어오지 않도록 로봇 런타임을 종료합니다.

예:

```text
Ctrl+C
```

## 5.2 팔을 반드시 지지

서보 전원이 사라지면 holding torque도 사라집니다.

따라서:

- 팔 아래에 받침대를 둔다.
- 전원을 끈 뒤 중력으로 관절이 회전하지 않는 위치로 둔다.
- 손으로 억지로 기어축을 돌리지 않는다.

향후에는 전원이 꺼져도 팔이 떨어지지 않는 별도 **PARK 자세/기계식 스토퍼**를 설계하는 것이 좋습니다.

## 5.3 종료 프로그램 실행

```bash
cd ~/pumpkin
bash scripts/servo_power_off.sh
```

화면에:

```text
If all four conditions are satisfied, type READY:
```

가 나오면 조건을 확인하고:

```text
READY
```

을 입력합니다.

프로그램이 인렛을 끄라고 하면 **팔을 계속 지지하면서 인렛을 OFF**합니다.

그 뒤:

```text
OFF
```

을 입력합니다.

프로그램은 잠시 기다린 후:

```text
OE HIGH
```

로 만들어 PCA9685 PWM을 차단합니다.

최종 순서는 다음과 같습니다.

```text
팔 동작 종료
   ↓
HOME 확인
   ↓
로봇 런타임 종료
   ↓
팔 물리적 지지
   ↓
서보/LRS 인렛 OFF
   ↓
5 V 감소 대기
   ↓
PCA9685 OE HIGH
   ↓
필요하면 Jetson 종료
```

### 왜 정상 종료에서 OE를 먼저 HIGH로 하지 않는가

서보 5 V가 살아 있는 동안 OE를 먼저 HIGH로 만들면 PWM이 사라져 서보의 holding torque가 먼저 풀릴 수 있습니다.

무거운 팔에서는 이때 관절이 떨어질 수 있으므로 정상 종료에서는 **팔 지지 → 서보 전원 OFF → OE HIGH** 순서를 사용합니다.

단, 실제 runaway 등 긴급상황에서는 사람/장비 충돌 방지를 위해 즉시 PWM을 차단해야 할 수 있습니다. 이 경우 아래 emergency 명령을 사용합니다.

---

# 6. 긴급 PWM 차단

```bash
cd ~/pumpkin
python3 scripts/pca9685/servo_power_sequence.py emergency-disable
```

프로그램에서:

```text
DISABLE
```

을 입력하면 OE를 즉시 HIGH로 만듭니다.

> [!WARNING]
> PWM 차단 즉시 서보가 holding torque를 잃을 수 있으므로 팔이 떨어질 수 있습니다. 전기적 runaway 차단용이며 정상 종료용이 아닙니다.

---

# 7. Jetson까지 끌 때

서보 안전 종료가 끝난 후 필요하면 Jetson을 정상 종료합니다.

```bash
sudo shutdown -h now
```

Jetson 파일시스템이 종료되기 전에 Jetson 자체 전원까지 강제로 차단하지 않습니다.

---

# 8. 현재는 '진짜 전원 스위치 프로그램'이 아닌 이유

현재 인렛은 220 V AC를 물리적으로 차단합니다.

Jetson GPIO를 인렛이나 LRS 고전류 출력에 직접 연결해서는 안 됩니다.

향후 Jetson 프로그램으로 서보 전원을 실제 ON/OFF하려면 다음과 같은 별도 하드웨어가 필요합니다.

```text
LRS +5 V / 22 A
      │
      ↓
DC 고전류 전원 스위치
(MOSFET load switch 또는 DC 정격 relay/contactor)
      │
      ↓
Fuse Box
      │
      ↓
Servos

Jetson GPIO
      │
      └── 저전류 제어 신호만 제공
```

Jetson GPIO가 서보 전류를 직접 흘리는 구조로 만들면 안 됩니다.

이 DC 스위치가 추가되면 `servo_power_sequence.py`를 확장해 인렛은 메인 전원으로 유지하고 서보 5 V만 프로그램으로 ON/OFF할 수 있습니다.

---

# 9. 커패시터/TVS 보호회로에 대한 현재 기준

이번 이상 현상 때문에 서보 전원 레일에 bulk capacitor와 과전압 clamp를 추가하는 방향은 타당합니다. 다만 **현재 30 V에 가까운 순간 표시가 실제 과전압인지 아직 계측으로 확정되지 않았습니다.**

따라서 현 단계에서는 임의의 보호부품을 바로 설치하지 않습니다.

특히 5 V 레일이라고 해서 `10 V` 또는 `16 V` 정격 전해콘덴서를 바로 설치하면 안 됩니다. 실제로 20~30 V 스파이크가 존재한다면 capacitor 정격을 초과할 수 있습니다.

최종 보호회로는 가능하면 오실로스코프/로직 분석을 통해 다음을 확인한 뒤 선정합니다.

- 정상 5 V rail ripple
- 서보 가속/감속 순간 최대전압
- 전원 OFF 순간 최대전압
- 특정 F1~F4 그룹에서만 발생하는지
- 특정 서보를 연결했을 때만 발생하는지

확인 후:

```text
LRS +5 V
   │
   ├── bulk capacitor
   ├── TVS / clamp
   └── fuse box
```

형태를 적용합니다.

커패시터는 전압 변화를 완화하고 TVS/clamp는 빠른 과전압을 제한하므로 역할이 다릅니다.

---

# 10. 현재 고장 조사 중 주의사항

현재 확인된 현상:

- F4 측정 중 순간적으로 비정상적으로 높은 전압 표시
- 전원 OFF 주변에서 팔이 갑자기 움직인 경험
- 이후 서보 전체 무반응
- PCA9685 I2C 통신은 성공
- 멀티미터 주파수 측정에서 0 Hz 표시

`0 Hz`만으로 PCA9685 PWM 출력 고장을 확정하지 않습니다. 일반 멀티미터가 짧은 servo PWM pulse를 제대로 측정하지 못할 수 있으므로 최종 PWM 확인은 오실로스코프/로직애널라이저가 적합합니다.

F4/MG90S 그룹은 원인 확인 전까지 마지막에 한 개씩 연결해 시험합니다.

---

# 11. 매일 사용하는 짧은 버전

## 켜기

```text
1. 인렛 OFF
2. 팔 지지
3. Jetson 부팅
4. bash scripts/servo_power_on.sh
5. READY
6. 인렛 ON
7. ON
8. PWM enabled 확인
9. 로봇 프로그램 실행
```

## 끄기

```text
1. 동작 종료 / HOME 확인
2. 로봇 프로그램 Ctrl+C
3. 팔 지지
4. bash scripts/servo_power_off.sh
5. READY
6. 인렛 OFF
7. OFF
8. OE HIGH 확인
9. 필요하면 Jetson shutdown
```

## 금지

```text
- 팔이 움직이는 중 인렛 OFF
- 팔이 공중에 떠 있는 상태에서 servo power OFF
- Jetson/PCA 준비 전에 servo power ON
- 원인 미확인 상태에서 F1~F4 전체 반복 ON/OFF
- Jetson GPIO로 LRS 22 A 전원을 직접 스위칭
```
