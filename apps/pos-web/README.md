# Pumpkin POS Web

무인카페 점장/관리자가 앱 사전주문과 로봇 현장주문을 확인하고 제조 상태를 관리하는 POS 웹입니다.

## 주문 계약

현재 `main`의 [사전주문·얼굴인식 픽업 계약](../../docs/preorder_face_pickup_contract.md)과 Cloud Relay API를 기준으로 합니다.

- `source`: `APP | ROBOT | POS`
- `status`: `RECEIVED | PREPARING | READY | PICKED_UP | CANCELLED`
- 주문 품목: `menu_id`, `menu_name`, `temperature`, `quantity`, `unit_price`
- 주문 합계: 서버 응답의 `total_price`
- 공식 메뉴 ID/가격/허용 온도: [`config/menu_catalog.json`](../../config/menu_catalog.json)

허용 상태 흐름:

```text
RECEIVED → PREPARING → READY → PICKED_UP
RECEIVED/PREPARING → CANCELLED
```

## 화면 구성

- `/dashboard`: 오늘 주문·매출·진행·픽업 대기 KPI와 제조 흐름 보드
- `/orders`: 전체 주문, 검색/필터, 주문 상세, 허용 상태 전이
- `/menus`: 공식 메뉴 카탈로그 조회
- `/customers`: `customer_id` 기준 주문 이력·누적금액·주문 기반 선호 집계

대시보드는 `주문 접수 → 제조 중 → 준비 완료` 3단계로 진행 주문을 나누고, `PICKED_UP` 주문은 최근 완료 영역에 표시합니다.

## 보안 경계

POS 브라우저는 Cloud Relay를 직접 호출하지 않습니다.

```text
POS Browser
  ↓ same-origin
POS Express Server
  ↓ X-Relay-Token (server only)
Cloud Run Relay
```

- `JETSON_RELAY_TOKEN`은 POS 서버 프로세스에만 둡니다.
- Relay 토큰을 `VITE_*` 변수나 브라우저 번들에 넣지 않습니다.
- POS Express 서버는 기본적으로 `127.0.0.1`에만 바인딩합니다.
- 다른 장비에 공개할 때는 신뢰 가능한 내부망 또는 별도 인증 프록시를 사용합니다.
- 프론트 호환용 `/api/auth/session`은 로컬 passwordless POS 모드에서 `authenticated: true`를 반환합니다.

## DEMO MODE

DEMO MODE는 화면만 바꾸는 mock이 아니라 POS 서버가 실제 Cloud Relay 상태 변경 API를 호출합니다.

APP 주문:

```text
RECEIVED
  → 1초
PREPARING
  → 5초
READY
  → 얼굴인식 픽업 대기
```

ROBOT 주문:

```text
RECEIVED
  → 1초
PREPARING
  → 5초
READY
  → 3초
PICKED_UP
```

APP의 `READY` 이후에는 Jetson 얼굴인식 픽업 흐름이 이어집니다.

```text
READY
→ 얼굴인식
→ 주문 내용 + 픽업 위치 안내
→ TTS done
→ 3초
→ Jetson PATCH PICKED_UP
→ 앱/POS 완료 반영
```

DEMO MODE 상태는 `apps/pos-web/.runtime/demo-mode.json`에 저장되며 `.runtime/`은 Git에서 제외합니다.

## 실행

저장소의 현재 `main`을 사용합니다.

```bash
cd ~/pumpkin_public
git switch main
git pull --ff-only

cd apps/pos-web
cp .env.example .env
```

`.env`의 최소 설정:

```env
POS_RELAY_BASE_URL=https://YOUR-CLOUD-RUN-URL
JETSON_RELAY_TOKEN=YOUR-SERVER-ONLY-TOKEN
POS_BIND_HOST=127.0.0.1
POS_PORT=4174
```

Firestore에서 고객 이름까지 표시하려면 실행 환경의 Google Application Default Credentials와 `PUMPKIN_FIREBASE_PROJECT_ID`를 함께 설정합니다. 주문 조회와 제조 상태 관리는 이 설정이 없어도 Cloud Relay 기준으로 동작합니다.

개발 실행:

```bash
npm install
npm run dev
```

빌드 및 서버 실행:

```bash
npm install
npm run build
npm start
```

- 개발 화면: `http://localhost:5173`
- 빌드 서버: 기본 `http://127.0.0.1:4174`

## ROBOT 주문 연동

ROS2 `order_submission_node`는 `/decision_result`를 구독하고 주문 세션의 최종 확정 주문을 Cloud Relay에 한 번 제출합니다.

```text
ORDER_CONFIRMED
→ 세션별 최신 주문 후보 보관
→ 추가/수정 시 후보 갱신
→ NEXT_CUSTOMER_READY + ORDER_FINISHED
→ source=ROBOT POST /api/v1/orders
→ POS 표시
```

중복 전송 방지를 위해 `request_id=robot-{session_id}`를 사용합니다.

## 통합 확인 항목

- APP 주문이 제조 보드에 표시되는지
- 수동 상태 변경이 허용된 전이만 수행하는지
- DEMO MODE의 APP/ROBOT 전이가 실제 Relay 상태와 일치하는지
- APP `READY`가 얼굴인식 픽업 전까지 유지되는지
- ROBOT 주문이 주문 종료 시 Cloud Relay와 POS에 한 번만 등록되는지
- 서버 재시작 후 DEMO MODE 상태가 복원되는지
- Relay 토큰이 브라우저 응답과 번들에 노출되지 않는지
