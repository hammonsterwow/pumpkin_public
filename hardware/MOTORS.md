# 서보 구성 및 채널 맵

현재 로봇은 PCA9685 한 대의 CH0, CH1, CH4–CH10을 사용하여 총 9개의 서보를 제어한다.

| 채널 | 위치 | 모델 | HOME 각도 |
|---:|---|---|---:|
| CH0 | Neck Pitch | MG996R | 60° |
| CH1 | Neck Yaw | MG996R | 90° |
| CH4 | Root | DS3218 | 90° |
| CH5 | Arm A1 | DS3218 | 90° |
| CH6 | Arm A2 | MG996R | 90° |
| CH7 | Arm B | MG996R | 1° |
| CH8 | Wrist A | MG90S | 1° |
| CH9 | Wrist B | MG90S | 140° |
| CH10 | Gripper | MG90S | 179° |

CH2, CH3, CH11–CH15는 사용하지 않는다.

## 모델별 수량

| 모델 | 수량 | 용도 |
|---|---:|---|
| DS3218 | 2 | 어깨 Root·Arm A1 |
| MG996R | 4 | 목 2축, Arm A2·Arm B |
| MG90S | 3 | 손목 2축, 그리퍼 |

## 제어 기준

~~~text
Jetson ROS2 → I2C → PCA9685 → Servo signal
~~~

- 목: CH0은 끄덕임(Pitch), CH1은 좌우 회전(Yaw)에 사용한다.
- 팔: CH4–CH10은 1000–2000 µs 펄스 폭 범위로 설정한다.
- 서보의 +5 V와 GND는 전원 분배부에서 공급하고 PCA9685는 PWM 신호를 제공한다.
- 실제 동작 각도와 보간 순서의 기준은 ros2_ws/src/robot_controller/robot_controller/arm_motion.py이다.
