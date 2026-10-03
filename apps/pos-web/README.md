# Pumpkin POS Web

무인카페 점장/관리자가 앱 사전주문과 로봇 현장주문을 확인하고 제조 상태를 관리하는 신규 POS 웹입니다.

## 기준 계약

사전주문/얼굴인식 픽업 연동 작업 전에는 항상 원격 최신 계약을 확인합니다.

```bash
cd ~/pumpkin
git fetch origin
git show origin/agent/preorder-face-pickup:docs/preorder_face_pickup_contract.md
```

현재 POS는 기존 통합 주문 API 계약을 그대로 사용합니다.

- `source`: `APP | ROBOT | POS`
- `status`: `RECEIVED | PREPARING | READY | PICKED_UP | CANCELLED`
- 주문 품목: `menu_id`, `menu_name`, `temperature`, `quantity`, `unit_price`
- 주문 합계: 서버 응답의 `total_price`
- `menu_id`: `config/menu_catalog.json`의 정수 공식 ID
- `menu_name`, `unit_price`: 주문 당시 스냅샷

## 화면 구성

- `/dashboard`: 오늘 주문/매출/진행/픽업 대기 KPI와 `주문 접수 → 제조 중 → 준비 완료` 3단계 제조 흐름 보드
  - 각 단계별 현재 주문 수와 주문 카드 표시
  - 카드 내부 3단계 진행선 표시
  - APP `READY`: `얼굴인식 픽업 대기`
  - ROBOT `READY` + DEMO MODE: `자동 픽업 처리 중`
  - `PICKED_UP` 주문은 `최근 완료`에 표시해 상태 전이 결과를 눈으로 확인
- `/orders`: 전체 주문, 검색/필터, 주문 상세, 허용된 상태 전이
- `/menus`: `config/menu_catalog.json` 기반 공식 메뉴 조회 전용
- `/customers`: `customer_id` 기준 주문 이력/누적금액/주문 기반 선호 집계

실제 얼굴등록/단골 프로필은 Firestore `users/{uid}`에 존재하지만 POS용 관리자 조회 API 계약이 아직 없으므로 주문 이력과 임의로 합치지 않습니다.

## 디자인 원칙

기존 관리자 웹은 참고하지 않습니다. `apps/demo-web`에서는 레이아웃이 아니라 시각 스타일만 참고합니다.

- Inter / Pretendard
- 흰색 / 연회색 / 차콜
- 얇은 1px 구분선
- 그림자와 강한 상태색 최소화
- 작은 영문 대문자 eyebrow
- 간결한 `LIVE`
- 새 주문과 제조 단계 이동의 짧은 fade/slide

## 비밀번호 없는 로컬 POS 모드

2026 한이음 시연/매장 내부 배치에서는 관리자 로그인 화면을 사용하지 않습니다.

```text
POS 브라우저
  ↓ 같은 장비의 POS API
POS Express 서버
  ↓ X-Relay-Token (server only)
Cloud Run Relay
```

중요:

- `JETSON_RELAY_TOKEN`은 POS 서버 프로세스에만 둡니다.
- 브라우저 번들이나 `VITE_*` 환경변수에 Relay 토큰을 넣지 않습니다.
- POS Express 서버는 기본적으로 `127.0.0.1`에만 바인딩합니다.
- 다른 장비에서 접속하려고 `POS_BIND_HOST=0.0.0.0`을 사용할 때는 신뢰 가능한 매장 내부망 또는 별도 인증 프록시를 사용합니다.

`/api/auth/session` 호환 엔드포인트는 항상 `authenticated: true`를 반환하며 비밀번호를 검사하지 않습니다.

## ROBOT 주문 Cloud Relay 연동

ROS `order_submission_node`가 `/decision_result`를 구독합니다.

```text
ORDER_CONFIRMED
→ 세션별 최신 주문 후보 보관
→ 추가 주문/수정 시 후보 교체
→ NEXT_CUSTOMER_READY + ORDER_FINISHED
→ config/menu_catalog.json 공식 menu_id/가격 스냅샷 생성
→ source=ROBOT POST /api/v1/orders
→ POS 표시
```

첫 주문 요약 확인 직후 바로 저장하지 않는 이유는 그 뒤 고객이 추가 주문을 선택할 수 있기 때문입니다. 실제 주문 종료 시점에 최종 주문을 1회 제출합니다.

## DEMO MODE

상단 `DEMO MODE` 토글은 화면 상태만 바꾸지 않고 POS Express 서버가 실제 Cloud Relay 상태 변경 API를 호출합니다.

APP:

```text
RECEIVED
  -> 1초
PREPARING
  -> 5초
READY
  -> STOP
```

APP `READY` 이후는 실제 얼굴인식 픽업 흐름이 이어집니다.

```text
READY
-> 얼굴인식
-> 실제 주문 내용 + 왼쪽 픽업 안내
-> TTS done
-> 3초
-> Jetson PATCH PICKED_UP
-> 앱/POS 완료 반영
```

ROBOT:

```text
RECEIVED
  -> 1초
PREPARING
  -> 5초
READY
  -> 3초
PICKED_UP
```

DEMO MODE는 사용자가 OFF 할 때까지 유지됩니다. 기본 상태는 `apps/pos-web/.runtime/demo-mode.json`에 저장되어 브라우저 새로고침과 POS 서버 재시작 후에도 복원되며, `.runtime/`은 Git에서 제외합니다.

## 실행

```bash
cd ~/pumpkin
git fetch origin
git switch feat/pos-web
git pull --ff-only origin feat/pos-web

cd apps/pos-web
cp .env.example .env
nano .env
```

최소 `.env`:

```env
POS_RELAY_BASE_URL=https://실제-CLOUD-RUN-주소
JETSON_RELAY_TOKEN=실제-Relay-토큰
POS_BIND_HOST=127.0.0.1
POS_PORT=4174
```

실행:

```bash
set -a
source .env
set +a
npm install
npm run dev
```

접속:

```text
http://localhost:5173
```

프로덕션 형태:

```bash
npm install
npm run build
npm start
```

## 아직 실제 환경에서 검증할 것

- 최신 제조 흐름 UI `npm run build`
- 실제 Cloud Run Relay 연결
- 앱 주문 → POS 제조 보드 표시
- APP DEMO MODE `주문 접수 → 제조 중 → 준비 완료` 이동
- ROBOT 실제 음성 주문 종료 → Cloud Relay → POS 표시
- ROBOT DEMO MODE `주문 접수 → 제조 중 → 준비 완료 → 최근 완료`
- DEMO MODE ON → POS 서버 재시작 → ON 복원
- READY 얼굴인식 → TTS/목/팔 → 3초 → PICKED_UP
