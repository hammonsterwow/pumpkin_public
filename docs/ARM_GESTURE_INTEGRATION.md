# 팔 제스처 런타임 통합

검증된 PCA9685 팔 자세를 현재 주문·안내 흐름에 연결한 기준입니다.

## 행동 매핑

| 서비스 상황 | 목 | 팔 |
|---|---|---|
| 고객 접근/주문 시작 | NOD 또는 CENTER | WAIT |
| 화장실 안내 | TURN_RIGHT/LEFT | POINT_RIGHT/LEFT |
| 픽업대 안내 | TURN_LEFT/RIGHT | POINT_LEFT/RIGHT |
| 인식 실패·재질문 | SHAKE | UNSURE |
| 주문 종료 확인 | DOUBLE_NOD | WAIT |
| 고객 퇴장 안내 | CENTER | GOODBYE_WAVE |

화장실 방향은 `PUMPKIN_RESTROOM_DIRECTION` 정책을 따르며 픽업 방향과 함께 일관되게 적용합니다.

## 실행 규칙

- 실제 팔 동작은 `POINT_RIGHT`, `POINT_LEFT`, `UNSURE`, `GOODBYE_WAVE`를 사용합니다.
- 팔 동작은 HOME 자세에서 시작하고 완료 후 HOME 복귀를 시도합니다.
- 목과 팔은 같은 PCA9685를 사용하므로 드라이버 접근을 동기화합니다.
- 구체적인 채널·HOME 값은 [`hardware/MOTORS.md`](../hardware/MOTORS.md), 동작 pose는 `arm_motion.py`를 기준으로 합니다.

## 실행

5인치 고객 화면을 포함한 실물 통합:

```bash
cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

5인치 화면 없이 로봇 상호작용만:

```bash
cd ~/pumpkin_public
bash scripts/run_robot_interaction_demo.sh
```

팔을 비활성화해 음성·Vision·목만 확인:

```bash
PUMPKIN_ENABLE_ARM=false bash scripts/run_robot_interaction_demo.sh
```

통합 런처에서는 실물 프로필에 맞춰 팔을 기본 활성화합니다.

## 코드 확인

```bash
cd ~/pumpkin_public
source .venv/bin/activate
python -m compileall -q ros2_ws/src/robot_controller/robot_controller
bash -n scripts/run_robot_interaction_demo.sh
bash -n scripts/run_robot_with_monitor.sh
```

## 실물 확인 기준

팔이 HOME인 상태에서 다음을 순서대로 확인합니다.

- 오른쪽/왼쪽 위치 안내
- 인식 실패 `UNSURE`
- 종료 `GOODBYE_WAVE`
- 목과 팔 동시 동작 시 충돌·과전류·기계적 간섭 여부
- 모든 동작 후 HOME 복귀

서보 전원 투입·차단은 [`hardware/SERVO_POWER_ON_OFF_MANUAL.md`](../hardware/SERVO_POWER_ON_OFF_MANUAL.md)을 따릅니다.
