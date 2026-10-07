# Pumpkin 하드웨어

Pumpkin 로봇의 최종 하드웨어 구성과 연결 문서를 정리한다.

## 제어 구조

~~~text
Jetson Orin Nano
├─ I2C → PCA9685 → 목·팔 서보 9개
├─ USB Serial → ESP32 → 3.5인치 얼굴 LCD
├─ HDMI → 5인치 메인 디스플레이
└─ USB → 카메라·마이크·스피커
~~~

서보는 Jetson의 ROS2 노드가 PCA9685를 통해 직접 제어한다. ESP32는 얼굴 LCD 출력만 담당한다.

## 서보 구성

- DS3218 × 2: 어깨 Root·Arm A1
- MG996R × 4: 목 2축 및 Arm A2·Arm B
- MG90S × 3: 손목 2축 및 그리퍼
- 사용 채널: PCA9685 CH0, CH1, CH4–CH10

상세 채널과 HOME 각도는 [MOTORS.md](./MOTORS.md)를 참고한다.

## 전원 구조

서보 전원은 MEAN WELL LRS-150F-5의 5 V 출력을 사용하며, 퓨즈박스를 거쳐 각 구동부에 분배한다. Jetson/PCA9685 로직 전원과 서보 고전류 전원은 분리하고 GND만 공통으로 연결한다. PCA9685의 VCC에는 로직 전압을, 각 서보의 전원선에는 퓨즈를 거친 5 V를 공급한다.

전원 투입과 차단은 [SERVO_POWER_ON_OFF_MANUAL.md](./SERVO_POWER_ON_OFF_MANUAL.md)의 순서를 따른다.

## 문서

| 문서 | 내용 |
|---|---|
| [wiring.md](./wiring.md) | 전체 신호·전원 연결 |
| [power-budget.md](./power-budget.md) | 전원 용량과 퓨즈 분기 |
| [MOTORS.md](./MOTORS.md) | 서보 모델·위치·채널 |
| [PARTS.md](./PARTS.md) | 주요 하드웨어 구성 |
| [LRS-150F-5_CONNECTION_GUIDE.md](./LRS-150F-5_CONNECTION_GUIDE.md) | 전원공급장치 연결 및 안전 |
| [SERVO_POWER_ON_OFF_MANUAL.md](./SERVO_POWER_ON_OFF_MANUAL.md) | 서보 전원 운용 절차 |
| [JETSON_ESP32_LCD_SETUP.md](./JETSON_ESP32_LCD_SETUP.md) | 얼굴 LCD 연동 |
| [robot_arm/ARM_MOTIONS.md](./robot_arm/ARM_MOTIONS.md) | 로봇팔 동작 정의 |
| [components/](./components/) | 개별 부품 참고 문서 |
