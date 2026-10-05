# 로봇팔 동작 정의

팔 동작은 Jetson의 ROS2 제어 노드가 PCA9685 CH4–CH10을 직접 구동하여 실행한다. 각 제스처는 목표 자세로 이동한 뒤 HOME으로 복귀한다.

| 의미 | ROS2 명령 | 코드 포즈 | 용도 |
|---|---|---|---|
| 대기 | HOME | HOME | 시작·종료 기준 자세 |
| 오른쪽 안내 | POINT_RIGHT | right | 로봇 기준 오른쪽 위치 안내 |
| 왼쪽 안내 | POINT_LEFT | left | 로봇 기준 왼쪽 위치 안내 |
| 모름 표현 | UNSURE | unsure | 인식 실패·판단 불가·재질문 |
| 인사 | GOODBYE_WAVE | greeting | 고객 퇴장 시 손 흔들기 |

GREETING은 수동 실행과 이전 연동을 위한 호환 별칭이다. 실제 주문 흐름에서는 시작 인사가 아니라 고객 퇴장 시 GOODBYE_WAVE를 사용한다.

## 동작 흐름

1. 현재 자세에서 목표 포즈까지 smoothstep 보간으로 이동한다.
2. 목표 자세를 일정 시간 유지한다.
3. 인사 동작은 CH8을 반복 구동하여 손을 흔든다.
4. 모든 동작은 동일한 HOME 자세로 복귀한다.
5. 동작 중 예외가 발생해도 HOME 복귀를 시도한다.

## 방향 기준

POINT_RIGHT와 POINT_LEFT는 로봇 자신의 시점을 기준으로 한다. 사용자 시점과 혼동하지 않도록 화면, 음성 안내와 같은 기준을 사용한다.

## 구현 기준

- 동작명과 목표 각도: ros2_ws/src/robot_controller/robot_controller/arm_motion.py
- PCA9685 출력: ros2_ws/src/robot_controller/robot_controller/motor_driver.py
- 팔 채널: CH4–CH10
- 펄스 폭 범위: 1000–2000 µs

문서에 각도를 중복 정의하지 않고 실제 실행 코드의 HOME, POSES, ARM_ACTION_TO_POSE를 단일 기준으로 사용한다.
