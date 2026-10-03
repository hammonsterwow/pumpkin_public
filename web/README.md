# Pumpkin Manager Web

> [!WARNING]
> **관리자 웹 재구축 예정 (2026-08-10)**
>
> 이 `web/` 디렉터리는 현재까지 구현된 관리자 웹을 **삭제하지 않고 보존하기 위한 기존 구현(Legacy / Reference)** 으로 취급합니다.
> 관리자 웹의 UI와 프런트엔드 구조는 앞으로 새로 설계하여 다시 구현합니다.
>
> - 기존 코드는 ROS2/FastAPI 연동 방식과 과거 기능을 확인하기 위해 보존합니다.
> - 신규 관리자 UI 기능을 이 구조에 계속 누적하지 않습니다.
> - 재구축 전까지는 치명적인 오류 수정, API/ROS 연동 확인 등 필요한 유지보수만 수행합니다.
> - 새 관리자 웹이 기존 필수 기능을 대체하기 전에는 이 디렉터리를 삭제하지 않습니다.
> - 백엔드 `api/`, ROS Bridge 및 주문 API는 프런트엔드와 분리하여 재사용 가능성을 검토합니다.
>
> 저장소 전체 정리 방침: [`docs/REPOSITORY_CLEANUP_2026-08-10.md`](../docs/REPOSITORY_CLEANUP_2026-08-10.md)

---

## 기존 구현의 역할

Pumpkin 로봇의 **ROS2 대화 흐름을 모니터링하고 테스트하는 기존 관리자 웹**입니다.

아래 내용은 재구축 전에 기존 구현의 기능과 연동 계약을 확인하기 위한 참고 문서입니다.

관리자 웹과 FastAPI는 NLU 모델을 직접 로딩하지 않습니다. Structure B 모델은 ROS2의 `nlu_node`에서 한 번만 실행되고, 웹은 ROS Topic에서 발생한 결과를 표시합니다.

## 시스템 흐름

```text
사용자 음성
→ stt_node
→ /voice_text
→ nlu_node
→ /intent_result
→ decision_node
→ /decision_result
→ action_node
→ /robot_action
→ TTS · LCD · 고개 · 팔 동작
```

```text
ROS Topics
→ api/ros_bridge.py
→ FastAPI
→ React 관리자 웹
```

기존 웹에서 확인하는 주요 정보:

- STT 상태와 최종 인식 문장
- Structure B NLU의 Intent, Order Status, 복수 `items`, confidence
- Decision Node의 FSM 판단과 발화
- Action Node의 TTS, 표정, 화면, 고개, 팔 명령
- ROS 노드 실행 상태
- 얼굴 감지 및 단골 고객 식별 결과
- 주문 현황과 매출 현황

## 대화 흐름 테스트 입력

관리자 웹의 텍스트 입력 기능은 개발 중 로봇 대화 Flow를 검증하기 위한 기능입니다.

```text
웹 입력 문장
→ POST /api/orders/analyze-step3
→ /voice_text 발행
→ 실제 nlu_node
→ 실제 decision_node
→ 실제 action_node
→ 결과를 웹에 반환
```

브라우저에서 메뉴나 의도를 별도로 추정하지 않습니다. 테스트 입력도 실제 ROS 파이프라인과 동일한 결과를 사용합니다.

요청 예시:

```bash
curl -X POST http://127.0.0.1:8000/api/orders/analyze-step3 \
  -H "Content-Type: application/json" \
  -d '{"text":"아이스 아메리카노 두 잔 주세요"}'
```

## 주요 API

| API | 역할 |
|---|---|
| `GET /health` | FastAPI와 ROS 핵심 노드 연결 상태 |
| `GET /api/ros/status` | 실행 중인 ROS 노드와 Topic 연결 상태 |
| `GET /api/admin/snapshot` | 관리자 대시보드용 전체 ROS 상태 |
| `POST /api/stt/trigger` | Jetson 마이크 녹음 시작 요청 |
| `GET /api/stt/latest` | 최근 STT·NLU·Decision·Action 결과 |
| `POST /api/orders/analyze-step3` | 텍스트를 실제 ROS 대화 흐름으로 테스트 |

## 지원 메뉴

서비스 메뉴의 최신 기준은 `config/menu_catalog.json`입니다.

| menu_id | 메뉴 | HOT | ICE | 가격 |
|---:|---|:---:|:---:|---:|
| 1 | 아메리카노 | 지원 | 지원 | 3,000원 |
| 2 | 카페라떼 | 지원 | 지원 | 4,000원 |
| 3 | 바닐라라떼 | 지원 | 지원 | 4,500원 |
| 4 | 레몬에이드 | 미지원 | 지원 | 4,500원 |
| 5 | 딸기스무디 | 미지원 | 지원 | 5,000원 |

- 온도: `HOT`, `ICE`
- 수량: 1~20
- 한 문장 주문 항목: 최대 3개
- 누락된 온도와 수량은 기본값으로 확정하지 않고 ROS 대화 흐름에서 재질문

메뉴 연동 규칙은 [`docs/menu_catalog_policy.md`](../docs/menu_catalog_policy.md)를 따릅니다.

## 기술 구성

### Frontend

- Vite
- React
- TypeScript

### Backend 및 통신

- FastAPI
- `rclpy` 기반 ROS-Web Bridge
- ROS2 Topic

PyTorch, Transformers, koELECTRA 모델은 웹 백엔드가 아니라 ROS `nlu_node`에서 사용합니다.

## 기존 Jetson 통합 실행

> 아래 명령은 **기존 관리자 웹을 포함한 현재 통합 환경을 재현하거나 연동을 확인할 때** 사용합니다. 새 관리자 웹 재구축 이후 실행 진입점은 변경될 수 있습니다.

```bash
cd ~/pumpkin
source .venv/bin/activate
bash scripts/run_pos_with_nlu.sh
```

스크립트는 다음 구성요소를 함께 실행합니다.

1. ROS2 STT·NLU·Decision·Action·TTS 노드
2. FastAPI ROS-Web Bridge
3. 기존 Vite 관리자 웹

접속 주소:

```text
웹: http://JETSON_IP:3000
API: http://JETSON_IP:8000
```

## 기존 개발 모드

ROS 핵심 노드가 먼저 실행되어 있어야 합니다.

```bash
cd ~/pumpkin
source .venv/bin/activate
bash scripts/run_ros_voice_nodes.sh
```

FastAPI:

```bash
cd ~/pumpkin
source .venv/bin/activate
python3 -m uvicorn api.web_main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000
```

React:

```bash
cd ~/pumpkin/web
npm install
npm run dev
```

## 프런트엔드 환경 변수

`web/.env` 예시:

```env
VITE_API_BASE_URL=
VITE_DEV_API_TARGET=http://127.0.0.1:8000
```

### `VITE_API_BASE_URL`

값을 비워두면 현재 웹 호스트와 동일한 `/api` 경로를 사용합니다.

### `VITE_DEV_API_TARGET`

Vite 개발 서버가 요청을 전달할 FastAPI 주소입니다. 웹을 다른 PC에서 실행하면 Jetson IP를 지정합니다.

```env
VITE_DEV_API_TARGET=http://JETSON_IP:8000
```

브라우저 Mock NLU는 사용하지 않으므로 `VITE_USE_MOCK_API` 설정은 없습니다.

## 상태 확인

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/ros/status
curl http://127.0.0.1:8000/api/admin/snapshot
```

`/health`가 `error`이면 FastAPI만 실행된 상태일 수 있습니다. `nlu_node`, `decision_node`, `action_node` 등 ROS 핵심 노드를 먼저 확인합니다.
