# 손 제스처 기반 주문 수량 입력

현재 `main`의 Vision/Decision 파이프라인은 수량 질문 중 손가락 1~5개를 구조화된 수량 입력으로 사용할 수 있습니다.

## 동작 원칙

손 제스처는 **FSM이 정확히 수량 슬롯을 기다리는 동안에만** 주문 값을 변경합니다.

```text
ASK_QUANTITY
+ waiting_for.slot == quantity
+ ONE_FINGER ... FIVE_FINGERS
        ↓
quantity = 1 ... 5
        ↓
기존 주문 slot merge / FSM 재사용
```

주문 확인, 대기, 안내 같은 다른 상태에서 손가락이 감지되어도 주문 수량에 적용하지 않습니다.

## 지원 제스처

| Vision 이벤트 | 수량 |
|---|---:|
| `ONE_FINGER` | 1 |
| `TWO_FINGERS` | 2 |
| `THREE_FINGERS` | 3 |
| `FOUR_FINGERS` | 4 |
| `FIVE_FINGERS` | 5 |

Vision은 `/user/hand_gesture`에 이벤트를 발행하고 Decision Node가 현재 `waiting_for` 상태를 확인한 뒤 적용합니다.

## 구현 파일

- `robot_controller/hand_quantity_gesture.py`: 손가락 pose 안정화·분류
- `robot_controller/vision_node.py`: MediaPipe Hands 실행 및 `/user/hand_gesture` 발행
- `robot_controller/decision_node.py`: 수량 질문 상태에서 gesture → quantity 적용

NLU 모델은 손 제스처 때문에 다시 추론하지 않습니다. Vision에서 이미 구조화된 수량을 얻었기 때문에 기존 수량 슬롯 입력 경로로 전달합니다.

## 실행

실물 통합:

```bash
cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

팔을 끄고 Vision/대화만 먼저 확인:

```bash
cd ~/pumpkin_public
PUMPKIN_ENABLE_ARM=false bash scripts/run_robot_interaction_demo.sh
```

이벤트 확인:

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin_public/ros2_ws/install/setup.bash
ros2 topic echo /user/hand_gesture
```

## 튜닝 환경 변수

```text
PUMPKIN_ENABLE_HAND_QUANTITY=1
PUMPKIN_HAND_GESTURE_HOLD_SEC=0.35
PUMPKIN_HAND_GESTURE_MIN_FRAMES=3
PUMPKIN_HAND_EXTENSION_RATIO=1.15
PUMPKIN_HAND_MIN_SPAN=0.12
```

먼 거리에서 손이 너무 작으면 `PUMPKIN_HAND_MIN_SPAN`을 낮추고, 순간적인 오인식이 있으면 hold 시간이나 최소 frame 수를 높입니다.

## 통합 확인 기준

1. 로봇이 수량을 질문할 때 손가락 1~5개가 각각 올바른 수량으로 반영되는지 확인합니다.
2. 같은 pose를 계속 유지할 때 불필요하게 반복 입력되지 않는지 확인합니다.
3. 주문 확인이나 대기 상태에서 손가락을 보여도 수량이 바뀌지 않는지 확인합니다.
4. 손 제스처 입력 후 기존 음성 주문과 동일하게 주문 확인 단계로 이어지는지 확인합니다.
