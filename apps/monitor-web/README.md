# Pumpkin 5-inch Monitor Web

로봇 가슴의 5인치 HDMI 화면에서 고객에게 필요한 주문 진행 상태만 보여주는 웹입니다. POS나 개발자 디버그 화면과 달리 내부 confidence, ROS topic 이름, JSON을 사용자 화면에 노출하지 않습니다.

## 표시 정보

- 지금 말해도 되는지, 음성을 듣는 중인지, 처리 중인지
- 최근 고객 발화와 로봇 응답
- 현재 주문의 메뉴·온도·수량
- 누락 슬롯의 `선택 필요` 표시
- 복수/추가 주문의 항목별 카드
- 주문 확인·완료·재질문 상태

## 데이터 원본

| 표시 정보 | ROS 데이터 |
|---|---|
| 음성 입력 상태 | `/stt/status` |
| 고객 자막 | `/voice_text` |
| NLU 임시 주문 | `/intent_result` |
| 누적 주문·대화 상태 | `/decision_result` |
| 로봇 자막 | `/response_result.speech` |
| 로봇 음성 상태 | `/tts/status` |
| 고객 존재 여부 | `/human_presence` |

`/decision_result.order.items`가 있으면 이를 누적 주문의 기준으로 사용하고, Decision 결과가 오기 전 짧은 구간에만 최신 NLU items를 표시합니다. 화면 자체에서 누락 값을 추측하거나 기본값으로 채우지 않습니다.

메뉴 표시명은 [`config/menu_catalog.json`](../../config/menu_catalog.json)을 사용합니다.

## 권장 실행

실물 로봇에서는 저장소 루트의 통합 런처를 사용합니다.

```bash
cd ~/pumpkin_public
bash scripts/run_robot_with_monitor.sh
```

이 스크립트가 monitor-web 서버, 5인치 Chromium kiosk와 실물 로봇 파이프라인을 함께 실행합니다.

## 모니터 웹 단독 실행

ROS2 파이프라인이 이미 실행 중이라면:

```bash
cd ~/pumpkin_public
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

## 확인 기준

실물 통합 시 다음을 확인합니다.

- 고객이 없을 때 대기 화면이 유지되는지
- STT listening/speech/transcribing과 TTS speaking 상태가 올바르게 바뀌는지
- 온도·수량 누락을 임의로 채우지 않는지
- 추가 주문과 복수 주문이 항목별로 유지되는지
- 주문 확인/완료 단계의 마지막 주문 내용이 유지되는지
- `run_robot_with_monitor.sh` 종료 시 kiosk와 monitor server가 함께 종료되는지
