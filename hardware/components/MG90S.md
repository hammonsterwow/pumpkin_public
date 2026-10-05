# TowerPro 호환 MG90S 서보모터

Pumpkin 로봇은 MG90S 서보 3개를 손목 2축과 그리퍼에 사용합니다.

## 현재 프로젝트 적용

| 항목 | 내용 |
|---|---|
| 수량 | 3개 |
| Wrist A | PCA9685 CH8 |
| Wrist B | PCA9685 CH9 |
| Gripper | PCA9685 CH10 |
| 제어 | Jetson Orin Nano → I2C → PCA9685 |
| 전원 | MEAN WELL LRS-150F-5 기반 5 V 서보 레일 |

전체 서보 채널과 HOME 값의 최종 기준은 [`../MOTORS.md`](../MOTORS.md)입니다.

## 판매 페이지 기준 사양

| 항목 | 사양 |
|---|---|
| 회전 범위 | 약 180° |
| 동작 전압 | 4.8~6.0 V |
| 스톨 토크 | 4.8 V에서 1.8 kgf·cm, 6 V에서 2.2 kgf·cm |
| 동작 속도 | 4.8 V에서 0.10 s/60°, 6 V에서 0.08 s/60° |
| 데드밴드 | 5 µs |
| 무게 | 약 13.4 g |
| 제어 방식 | 50 Hz PWM |
| 일반적인 펄스 폭 | 약 1~2 ms |
| 배선 색상 | PWM: 주황색, VCC: 빨간색, GND: 갈색 |

판매 페이지 표기와 실제 서보의 기계적 끝점은 다를 수 있으므로 실행 코드에서는 로봇 기구의 안전 범위를 우선합니다.

## 연결 구조

```text
Jetson Orin Nano
    │ I2C
    ▼
PCA9685
    ├── CH8  → Wrist A / MG90S
    ├── CH9  → Wrist B / MG90S
    └── CH10 → Gripper / MG90S

LRS-150F-5
    └── Fuse block F4 → MG90S +5 V

GND bus
    └── Servo GND / PCA9685 GND / Jetson GND
```

- PWM 신호는 PCA9685에서 공급합니다.
- 서보 전원은 Jetson이나 ESP32에서 직접 공급하지 않습니다.
- ESP32는 얼굴 LCD 출력 전용이며 PCA9685 서보 제어를 담당하지 않습니다.
- 실제 동작 각도와 보간은 `ros2_ws/src/robot_controller/robot_controller/arm_motion.py`를 기준으로 합니다.

## 운용 주의

- 기계적 끝점까지 강제로 구동하지 않습니다.
- 손목과 그리퍼의 케이블이 링크 동작에 끼이지 않도록 고정합니다.
- 3개 동시 동작 시 5 V 레일 전압 강하와 배선·단자 발열을 확인합니다.
