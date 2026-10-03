# 손 제스처 기반 주문 수량 입력

브랜치: `feat/hand-gesture-quantity`

## 목표

주문 FSM이 수량을 묻는 `ASK_QUANTITY` 상태일 때 고객이 카메라에 검지와 중지 두 개를 펴면 `quantity=2`로 입력한다.

```text
고객: "아이스 아메리카노 주세요."
로봇: "몇 잔 주문하시겠어요?"
고객: ✌️
Vision: TWO_FINGERS
Decision: quantity=2
로봇: "아이스 아메리카노 두 잔 맞으신가요?"
고객: 끄덕임
Decision: AFFIRM
```

핵심 원칙은 **손가락 두 개를 항상 2잔으로 해석하지 않는 것**이다. `ASK_QUANTITY`이면서 `waiting_for.slot == quantity`인 경우에만 주문 값을 변경한다. 다른 대화 상태에서 V-sign이 감지되어도 무시한다.

## 구현 구조

```text
USB Camera
  └─ vision_node_hand_quantity
       ├─ 기존 얼굴/사람 감지
       ├─ 기존 NOD/SHAKE
       └─ MediaPipe Hands
            └─ TWO_FINGERS
                 ↓ /user/hand_gesture

decision_node_hand_quantity
  ├─ 기존 AdditionalOrderDecisionNode 전체 기능 유지
  └─ ASK_QUANTITY 상태에서만
       TWO_FINGERS → synthetic quantity=2
                 ↓
       기존 주문 slot merge/FSM 재사용
```

NLU 모델은 재학습하지 않는다. 비전에서 이미 구조화된 수량을 얻었으므로, 짧은 음성 답변 `두 잔이요`와 같은 slot 입력 경로로 직접 전달한다.

## Jetson에서 브랜치 받기

```bash
cd ~/pumpkin
git fetch origin
git switch feat/hand-gesture-quantity
git pull origin feat/hand-gesture-quantity
```

## 1. 코드 테스트

```bash
cd ~/pumpkin
source .venv/bin/activate

python -m compileall -q ros2_ws/src/robot_controller/robot_controller

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  ros2_ws/src/robot_controller/test/test_hand_quantity_recognizer.py \
  ros2_ws/src/robot_controller/test/test_hand_quantity_gesture_flow.py \
  ros2_ws/src/robot_controller/test/test_multimodal_gesture_flow.py
```

Jetson에서는 ROS2 Humble의 `launch_testing` pytest 플러그인이 자동 발견될 수 있다. 이 플러그인은 위 단위 테스트에 필요하지 않으며, `.venv`에 ROS 쪽 `lark` 의존성이 없으면 테스트 본문이 시작되기도 전에 `ModuleNotFoundError: No module named 'lark'`로 종료될 수 있다. 따라서 이 기능의 단위 테스트는 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 외부 pytest 플러그인 자동 로드를 끄고 실행한다.

기존 실물 실행 스크립트는 실행 시 `robot_controller`를 다시 빌드하므로 별도 `colcon build`는 필수가 아니다. 수동 빌드하려면 다음을 사용한다.

```bash
cd ~/pumpkin/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_controller --symlink-install
source install/setup.bash
```

## 2. 첫 실물 테스트: 팔은 끄고 확인

처음에는 손 제스처와 주문 로직만 확인한다.

```bash
cd ~/pumpkin
PUMPKIN_ENABLE_ARM=false bash scripts/run_robot_interaction_demo.sh
```

다른 터미널에서 감지 이벤트를 확인한다.

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin/ros2_ws/install/setup.bash
ros2 topic echo /user/hand_gesture
```

카메라를 향해 손바닥이 보이게 하고 검지·중지만 편 상태를 약 0.5초 유지한다.

정상이라면 다음 값이 한 번 출력된다.

```text
data: TWO_FINGERS
```

손을 계속 들고 있어도 동일 pose에서 반복 발행하지 않는다. 손을 내렸다가 다시 두 손가락을 보여야 다시 인식한다.

## 3. 주문 통합 테스트

다음 순서로 확인한다.

1. 고객이 로봇 앞에 선다.
2. `아이스 아메리카노 주세요.`라고 말한다.
3. 로봇이 수량을 묻는지 확인한다.
4. **말하지 않고** 카메라에 ✌️를 약 0.5초 보여준다.
5. 로봇이 `아이스 아메리카노 두 잔`으로 주문을 이어가는지 확인한다.
6. 주문 확인 질문에는 기존처럼 고개를 끄덕여 확정한다.

중요: ✌️는 `ASK_QUANTITY` 상태에서만 받아들인다. 주문 확인 중이나 대기 중에 V-sign을 해도 주문 수량이 바뀌면 안 된다.

## 4. 전체 시연 실행

손 수량 입력이 안정화된 뒤 5인치 화면과 팔까지 포함한 현재 통합 런타임을 사용한다.

```bash
cd ~/pumpkin
bash scripts/run_robot_with_monitor.sh
```

## 튜닝 환경 변수

기본값:

```text
PUMPKIN_ENABLE_HAND_QUANTITY=1
PUMPKIN_HAND_GESTURE_HOLD_SEC=0.35
PUMPKIN_HAND_GESTURE_MIN_FRAMES=3
PUMPKIN_HAND_EXTENSION_RATIO=1.15
PUMPKIN_HAND_MIN_SPAN=0.12
```

### 손을 잘 못 찾는 경우

먼 거리에서 손이 너무 작게 보이면 먼저 아래처럼 최소 손 크기를 낮춘다.

```bash
PUMPKIN_HAND_MIN_SPAN=0.08 \
PUMPKIN_ENABLE_ARM=false \
bash scripts/run_robot_interaction_demo.sh
```

그 다음 실제 시연 거리에서 반복 테스트하며 `0.08~0.12` 사이를 조정한다.

### 오인식이 있는 경우

V-sign이 아닌 손 모양을 두 손가락으로 잘못 잡으면 안정화 시간을 늘린다.

```bash
PUMPKIN_HAND_GESTURE_HOLD_SEC=0.50 \
PUMPKIN_HAND_GESTURE_MIN_FRAMES=4 \
PUMPKIN_ENABLE_ARM=false \
bash scripts/run_robot_interaction_demo.sh
```

## 현재 범위

이번 브랜치에서는 의도적으로 `TWO_FINGERS → 2잔`만 지원한다.

- `☝️ → 1잔`: 미지원
- `✌️ → 2잔`: 지원
- `3/4/5 손가락`: 미지원

실물에서 2잔 입력이 안정적으로 동작하는 것을 먼저 검증한 뒤 1~5 수량 인식으로 확장한다.

## 롤백

문제가 생기면 같은 브랜치에서도 기존 노드를 직접 실행할 수 있도록 entry point를 남겨두었다.

```bash
ros2 run robot_controller vision_node_no_hand
ros2 run robot_controller decision_node_no_hand
```

`main`에는 아직 병합하지 않는다. Jetson 실물 테스트와 카메라 거리/조명 튜닝이 완료된 뒤 PR을 생성한다.
