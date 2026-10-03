# 팔 제스처 런타임 통합

이 문서는 검증된 PCA9685 팔 자세를 현재 주문·안내 흐름에 연결한 기준이다.

## 행동 매핑

| 서비스 상황 | 음성/상태 | 목 | 팔 |
|---|---|---|---|
| 고객 접근, 주문 시작 | 안녕하세요. 주문 도와드릴게요. | NOD | WAIT |
| 화장실 안내(기본 설정) | 오른쪽 안내 | TURN_RIGHT | POINT_RIGHT |
| 픽업대 안내(기본 설정) | 왼쪽 안내 | TURN_LEFT | POINT_LEFT |
| 음성 인식 실패 | 다시 말씀해 주세요. | SHAKE | UNSURE |
| 주문 확정 후 추가 여부 확인 | 주문을 마치시겠어요? | DOUBLE_NOD | WAIT |
| 고객이 주문 종료 확정 | 주문이 완료되었습니다. 감사합니다. | CENTER | GOODBYE_WAVE |

화장실 방향을 `PUMPKIN_RESTROOM_DIRECTION=LEFT`로 바꾸면 기존 로직대로
픽업대는 반대편 RIGHT가 되며, 목과 팔 명령도 함께 뒤집힌다.

## 동작 규칙

- `POINT_RIGHT`, `POINT_LEFT`, `UNSURE`, `GOODBYE_WAVE`만 실제 팔 동작으로 실행한다.
- 첫 고객 인사의 기존 `WELCOME` 팔 동작은 사용하지 않는다.
- 모든 팔 동작은 차렷(HOME)에서 시작한다고 가정하며 완료 후 HOME으로 복귀한다.
- 자세 진입은 140 step × 0.01초, HOME 복귀는 220 step × 0.01초 S자 보간을 사용한다.
- 손인사는 CH8을 1°↔105°로 세 번 왕복한 뒤 HOME으로 복귀한다.
- 팔은 별도 작업 스레드에서 움직여 목 SHAKE/TURN 동작과 동시에 실행될 수 있다.
- 같은 PCA9685를 사용하는 목·팔 쓰기는 하나의 드라이버 잠금으로 직렬화한다.

## 활성화

팔은 안전을 위해 기본 비활성화 상태다. 전원을 켜기 전에 팔을 차렷 자세에 두고,
고정 나사·서보혼·동작 반경을 확인한 다음 실행한다.

```bash
PUMPKIN_ENABLE_ARM=true bash scripts/run_robot_interaction_demo.sh
```

팔 없이 기존 얼굴·주문·POS·목 기능만 확인할 때는 환경 변수를 생략한다.

## 전체 실물 통합 실행

5인치 HDMI 고객 화면까지 한 번에 실행할 때는 다음 명령을 사용한다.

```bash
bash scripts/run_robot_with_monitor.sh
```

이 실행기는 다음을 함께 관리한다.

- 고객용 `apps/monitor-web` 서버
- 5인치 HDMI `DP-1` 출력의 180도 회전(`inverted`)
- Chromium 800×480 kiosk 화면
- 카메라·STT·NLU·TTS·얼굴 인식·ESP32 얼굴 LCD
- PCA9685 목 동작과 팔 제스처
- 주문 중계 및 POS 연동

팔은 이 통합 실행기에서 기본 활성화된다. 팔 없이 확인할 때만 다음처럼 끈다.

```bash
PUMPKIN_ENABLE_ARM=false bash scripts/run_robot_with_monitor.sh
```

모니터 출력명·회전·X 세션이 바뀐 경우에는 각각
`PUMPKIN_MONITOR_OUTPUT`, `PUMPKIN_MONITOR_ROTATION`,
`PUMPKIN_MONITOR_DISPLAY`, `PUMPKIN_MONITOR_XAUTHORITY`로 덮어쓴다.

비정상 종료 후 남은 전용 프로세스는 다음 명령으로 정리한다.

```bash
bash scripts/stop_robot_interaction_nodes.sh
```

## 검증

```bash
cd ~/pumpkin
source .venv/bin/activate
python -m compileall -q ros2_ws/src/robot_controller/robot_controller
bash -n scripts/run_robot_interaction_demo.sh
pytest -q \
  ros2_ws/src/robot_controller/test/test_arm_motion.py \
  ros2_ws/src/robot_controller/test/test_hardware_action_contract.py \
  ros2_ws/src/robot_controller/test/test_restroom_guide_flow.py \
  ros2_ws/src/robot_controller/test/test_pickup_guide_flow.py
```

실물 검증은 팔이 HOME인 상태에서 오른쪽 안내, 왼쪽 안내, 이해 실패,
종료 손인사를 각각 한 번씩 실행한 뒤 전체 시나리오로 진행한다.
