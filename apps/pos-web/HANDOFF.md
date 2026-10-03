# Pumpkin POS 웹 작업 인수인계

> 작업 브랜치: `feat/pos-web`  
> 통합 PR: #122  
> 기준 계약 브랜치: `origin/agent/preorder-face-pickup`

## 0. 작업 전 반드시 확인

```bash
cd ~/pumpkin
git fetch origin
git show origin/agent/preorder-face-pickup:docs/preorder_face_pickup_contract.md
```

사전주문/POS/얼굴인식 연동의 유효한 원본은 위 계약이다. `source`, `status`, 주문 필드, `customer_id` 규칙을 임의로 바꾸지 않는다.

## 1. 현재 구현 범위

경로:

```text
apps/pos-web/
```

페이지:

- `/dashboard`: 오늘 KPI + `주문 접수 → 제조 중 → 준비 완료` 제조 흐름 보드 + 최근 완료
- `/orders`: 전체 주문, 검색/필터, 상세, 상태 변경
- `/menus`: `config/menu_catalog.json` 조회 전용
- `/customers`: 주문 이력 기반 고객 집계

공통:

- APP / ROBOT / POS 구분
- 2초 주기 주문 갱신
- 신규 주문 알림
- Relay 연결 상태
- 상단 DEMO MODE
- demo-web의 형태가 아닌 스타일만 참고
- Relay 토큰은 POS 서버에만 보관

## 2. 관리자 로그인 제거

2026-08-16 사용자 결정으로 POS의 관리자 비밀번호 로그인은 제거했다.

현재 구조:

```text
POS Browser
  -> POS Express Server
  -> X-Relay-Token
  -> Cloud Relay
```

비밀번호 관련 환경변수는 더 이상 사용하지 않는다.

```text
POS_ADMIN_PASSWORD        사용 안 함
POS_SESSION_SECRET        사용 안 함
POS_SESSION_HOURS         사용 안 함
POS_COOKIE_SECURE         사용 안 함
```

대신 POS Express 서버는 기본적으로 로컬 호스트에만 바인딩한다.

```env
POS_BIND_HOST=127.0.0.1
```

다른 장비에서 접속해야 해서 `0.0.0.0`으로 열 경우 신뢰 가능한 매장 내부망 또는 인증 프록시가 필요하다.

프론트 호환용 `/api/auth/session`은 항상 `authenticated: true`를 반환한다.

## 3. 주문 계약

- `source`: `APP | ROBOT | POS`
- `status`: `RECEIVED | PREPARING | READY | PICKED_UP | CANCELLED`
- `menu_id`: `config/menu_catalog.json` 정수 ID
- `menu_name`: 주문 당시 이름 스냅샷
- `unit_price`: 주문 당시 가격 스냅샷
- `total_price`: 서버 계산값
- APP/얼굴인식 `customer_id`: Firebase Auth UID

허용 상태 전이:

```text
RECEIVED -> PREPARING -> READY -> PICKED_UP
RECEIVED/PREPARING -> CANCELLED
```

## 4. 대시보드 제조 흐름 UI

진행 주문을 한 카드 그리드에 섞지 않고 상태별 3개 열로 분리한다.

```text
01 주문 접수
      ↓
02 제조 중
      ↓
03 준비 완료
```

각 열 상단에는 현재 주문 수를 표시한다.

각 주문 카드에는 다음을 표시한다.

- 주문번호
- `APP PREORDER | ROBOT ORDER | POS ORDER`
- 메뉴 / 온도 / 수량
- `접수 → 제조 중 → 준비 완료` 3단계 진행선
- 현재 단계 설명
- 주문 합계
- DEMO MODE에서 다음 상태까지 남은 시간
- 계약상 허용된 수동 상태 변경 버튼

READY 설명:

```text
APP READY
→ 준비 완료 · 얼굴인식 픽업 대기

ROBOT READY + DEMO MODE
→ 준비 완료 · 자동 픽업 처리 중
```

상태가 바뀌면 카드가 다음 열에서 짧은 fade/slide로 나타나도록 한다.

`PICKED_UP` 주문은 진행 보드에서 제외하고 하단 `최근 완료`에 오늘 완료된 최신 4건을 표시한다. 따라서 ROBOT 자동 완료와 APP 얼굴인식 완료 결과가 화면에서 바로 사라지지 않고 확인 가능하다.

전용 스타일:

```text
apps/pos-web/src/manufacturing-board.css
```

## 5. DEMO MODE

구현 위치:

```text
apps/pos-web/server/index.mjs
```

APP:

```text
RECEIVED
 -> 1초
PREPARING
 -> 5초
READY
 -> STOP
```

APP READY 이후:

```text
얼굴인식
-> Firebase UID로 READY APP 주문 조회
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

안전 규칙:

- 화면에서만 가짜 상태를 만들지 않음
- 실제 Relay PATCH 사용
- DEMO MODE OFF는 현재 주문 상태를 되돌리지 않음
- APP READY는 DEMO MODE가 자동 완료하지 않음
- CANCELLED/PICKED_UP은 자동 전이 대상 아님
- stale transition 409는 무시

DEMO MODE 상태는 기본적으로 다음 로컬 런타임 파일에 저장한다.

```text
apps/pos-web/.runtime/demo-mode.json
```

한 번 ON하면 사용자가 OFF 할 때까지 유지되고, 브라우저 새로고침과 POS 서버 재시작 후에도 ON이 복원된다. `.runtime/`은 Git에서 제외한다.

## 6. ROBOT 주문 Cloud Relay 제출

새 ROS 노드:

```text
ros2_ws/src/robot_controller/robot_controller/order_submission_node.py
```

흐름:

```text
/decision_result
→ ORDER_CONFIRMED
→ 세션별 최신 주문 후보 보관
→ 추가 주문/수정 후 다시 ORDER_CONFIRMED가 나오면 후보 교체
→ NEXT_CUSTOMER_READY + semantic_event=ORDER_FINISHED
→ config/menu_catalog.json 공식 menu_id/menu_name/unit_price 적용
→ POST /api/v1/orders source=ROBOT
→ POS 표시
```

첫 `ORDER_CONFIRMED`에서 바로 POST하지 않는 이유는 현재 로봇 대화가 이후 추가 주문을 받을 수 있기 때문이다.

`request_id=robot-{session_id}`를 사용해 Cloud Relay 멱등 처리도 활용한다.

로봇 데모 실행 스크립트는 같은 Jetson의 `apps/pos-web/.env`가 있으면 Relay URL/토큰을 재사용한다.

확인 로그:

```bash
tail -f /tmp/pumpkin-logs/order_submission_node.log
```

성공 예:

```text
ROBOT 주문 Cloud Relay 등록 완료: ORD-..., status=RECEIVED
```

## 7. 실행

```bash
cd ~/pumpkin
git fetch origin
git switch feat/pos-web
git pull --ff-only origin feat/pos-web

cd apps/pos-web
cp .env.example .env
nano .env
```

최소 설정:

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
npm run build
npm run dev
```

접속:

```text
http://localhost:5173/dashboard
```

관리자 비밀번호 입력 과정은 없다.

## 8. 통합 테스트 순서

1. `npm run build` 성공 확인
2. POS 실행 후 로그인 화면 없이 대시보드 진입 확인
3. 실제 앱에서 APP 주문 생성
4. 제조 보드 `주문 접수` 열에 카드 등장 확인
5. DEMO MODE ON
6. 카드가 `주문 접수 -> 제조 중 -> 준비 완료`로 이동하는지 확인
7. APP READY에서 `얼굴인식 픽업 대기`로 정지 확인
8. 등록 고객 얼굴인식
9. 픽업 TTS/왼쪽 목·팔 동작 확인
10. TTS 종료 후 3초 뒤 PICKED_UP 확인
11. APP 주문이 `최근 완료`에 나타나고 앱도 완료 상태인지 확인
12. 실제 로봇 음성 주문을 끝까지 수행
13. `order_submission_node.log`에서 Cloud Relay 등록 성공 확인
14. POS에 `ROBOT ORDER` 카드 등장 확인
15. ROBOT DEMO MODE가 READY 후 3초 뒤 `최근 완료`로 이동하는지 확인
16. DEMO MODE ON 상태에서 POS 서버 재시작 후 ON 복원 확인

## 9. 아직 실기 검증 필요

코드 반영 완료와 실기 검증 완료를 구분한다.

아직 실제 환경에서 확인할 것:

- 최신 TypeScript/Vite build
- 제조 보드 실제 브라우저 렌더링
- APP 제조 단계 이동
- ROBOT 실제 음성 주문 → Relay → POS
- DEMO MODE 서버 재시작 영속성
- Jetson 얼굴/TTS/목/팔/자동 완료

## 10. 한 줄 요약

현재 POS는 `대시보드 + 주문 + 메뉴 + 고객` 4개 페이지에 더해, **상태별 제조 흐름 보드**, **최근 완료 표시**, **서버 재시작 후에도 유지되는 DEMO MODE**, **실제 ROBOT 주문의 Cloud Relay 제출 경로**까지 코드에 반영된 상태다.
