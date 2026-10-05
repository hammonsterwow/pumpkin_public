# 하드웨어 배선

## 전체 연결

~~~text
Jetson Orin Nano
├─ I2C SDA/SCL ── PCA9685 ── PWM ── Servo CH0, CH1, CH4–CH10
├─ USB Serial ─── ESP32 ──── SPI ── 3.5-inch face LCD
├─ HDMI ─────────────────────────── 5-inch main display
└─ USB ──────────────────────────── Camera / Microphone / Speaker

AC inlet ── LRS-150F-5 ── Fuse block ── Servo +5 V
                          GND bus ───── Servo GND / PCA9685 GND / Jetson GND
~~~

## PCA9685와 서보

- Jetson의 I2C SDA/SCL을 PCA9685에 연결한다.
- PCA9685 VCC에는 Jetson 로직 전압 3.3 V를 사용한다.
- Jetson, PCA9685, 서보 전원의 GND를 공통으로 연결한다.
- 서보 신호선은 PCA9685 각 채널에 연결한다.
- 서보 +5 V는 PCA9685 보드의 로직 전원에서 공급하지 않고 퓨즈박스에서 직접 분배한다.

| 채널 | 연결 |
|---:|---|
| CH0 | Neck Pitch / MG996R |
| CH1 | Neck Yaw / MG996R |
| CH4 | Root / DS3218 |
| CH5 | Arm A1 / MG996R |
| CH6 | Arm A2 / MG996R |
| CH7 | Arm B / MG996R |
| CH8 | Wrist A / MG90S |
| CH9 | Wrist B / MG90S |
| CH10 | Gripper / MG90S |

## 디스플레이와 입출력

- 얼굴 LCD: Jetson과 ESP32를 USB Serial로 연결하고, ESP32가 ILI9488 LCD를 SPI로 구동한다.
- 메인 화면: Jetson의 HDMI 출력과 LCD의 HDMI 입력을 연결하고 화면 전원은 별도 5 V USB로 공급한다.
- 카메라·마이크·스피커: Jetson USB 포트 또는 전원 여유가 있는 유전원 허브에 연결한다.

## 배선 점검

1. 전원을 끈 상태에서 극성, 단락, 단자 체결을 확인한다.
2. 보호접지(PE)와 금속 외함을 연결한다.
3. 서보 전원 투입 전 Jetson과 PCA9685가 준비되었는지 확인한다.
4. 최초 시험은 한 분기씩 진행하고 전압 강하·과전류·발열을 확인한다.
5. 정상 운용과 종료는 [SERVO_POWER_ON_OFF_MANUAL.md](./SERVO_POWER_ON_OFF_MANUAL.md)를 따른다.
