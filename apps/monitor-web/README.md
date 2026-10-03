# Pumpkin 5-inch Monitor Web

로봇 가슴의 5인치 HDMI 화면에서 **고객에게만 필요한 주문 진행 상태**를 보여주는 독립 웹입니다.

이 화면은 POS나 개발자 디버그 화면이 아닙니다. 내부 ROS 상태명, confidence, topic 이름, JSON 등을 노출하지 않고 다음만 보여줍니다.

- 지금 말해도 되는지 / 듣는 중인지 / 음성 처리 중인지
- 최근 고객 발화와 로봇 응답
- 현재 주문의 메뉴 / 온도 / 수량
- 누락된 슬롯의 `선택 필요` 표시
- 복수/추가 주문을 주문별 카드로 분리 표시
- 주문 확인 / 완료 / 재질문 상태

## 데이터 원본

기존 ROS2 계약을 그대로 구독하며 새 ROS 노드나 API 계약을 추가하지 않습니다.

| 표시 정보 | 기존 데이터 |
|---|---|
| 음성 입력 상태 | `/stt/status` |
| 고객 자막 | `/voice_text` |
| NLU 임시 주문 슬롯 | `/intent_result` |
| 누적 주문 / waiting_for / 대화 상태 | `/decision_result` |
| 로봇 자막 | `/response_result.speech` |
| 로봇 음성 출력 상태 | `/tts/status` |
| 고객 존재 여부 | `/human_presence` |

`/decision_result.order.items`가 존재하면 이를 현재 누적 주문의 기준으로 사용하고, Decision 결과가 아직 오기 전 짧은 구간에만 최신 NLU items를 미리 보여줍니다.

중요하게도 모니터 웹은 누락 슬롯을 자체적으로 추론하거나 기본값으로 채우지 않습니다. `None` 또는 누락된 값은 그대로 `선택 필요`로 표시합니다.

메뉴 표시명은 `config/menu_catalog.json`을 읽어 사용합니다.

## 실행

먼저 실제 로봇 ROS2 파이프라인을 실행한 뒤 별도 터미널에서 모니터 웹을 실행합니다.

```bash
cd ~/pumpkin
source .venv/bin/activate
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash

cd apps/monitor-web
python3 server.py
```

기본 주소:

```text
http://127.0.0.1:8770
```

포트 변경:

```bash
PUMPKIN_MONITOR_WEB_PORT=8771 python3 server.py
```

5인치 HDMI 화면에서는 Chromium 계열 브라우저의 kiosk/fullscreen 모드로 위 주소를 열어 사용합니다.

## 테스트

ROS 없이 데이터 변환과 주문 상태 유지 규칙만 확인할 수 있습니다.

```bash
cd ~/pumpkin/apps/monitor-web
python3 -m pytest -q test_monitor_state.py
```

테스트는 다음을 확인합니다.

1. 한 번에 완성된 단일 주문
2. 온도 누락
3. 수량 누락
4. 기존 주문 뒤 추가 주문
5. 한 문장의 복수 주문
6. STT 실패 시 값 임의 생성 금지
7. 주문 완료 상태에서도 마지막 확인 주문 유지

## 변경 경계

이번 구현은 `apps/monitor-web/**` 안에서만 동작합니다.

수정하지 않습니다.

- `apps/pos-web/**`
- `apps/customer-mobile/**`
- ROS2 production node
- 주문 서버 / Cloud Relay
- 기존 API 계약
- `config/menu_catalog.json`

따라서 POS/앱/ROS 작업과 독립적으로 검증한 뒤 통합할 수 있습니다.
