# 앱 사전주문 · 얼굴인식 픽업 연동 계약

> 상태: 현재 `main` 기준 연동 계약  
> 기준 정책: `docs/service_customer_and_display_policy.md`  
> 기준 코드: 고객 앱 · Cloud Run relay · Jetson ROS2 연동 구현  
> 최종 정리: 2026-10-05

이 문서는 고객 앱, Cloud Run 주문 중계, POS 웹, Jetson 얼굴인식 및 ROS 픽업 안내가 공유하는 단일 계약이다. 코드와 문서가 충돌하면 추측해서 별도 스키마를 만들지 말고 이 문서를 먼저 갱신한다.

## 1. 문서 기준

이 문서는 현재 `main` 브랜치의 고객 앱, Cloud Run 주문 중계, POS, Jetson 얼굴인식 및 ROS 픽업 안내가 공유하는 연동 기준을 정리한다.

- 주문 API 계약은 `/api/v1/orders`와 현재 API 구현을 기준으로 한다.
- 얼굴 프로필과 선호정보는 Firestore `users/{uid}`를 기준으로 한다.
- 토큰·서비스 계정 JSON·비밀 키는 문서나 클라이언트 번들에 기록하지 않는다.
- 코드와 문서가 다를 경우 현재 `main`의 구현을 확인하고 이 문서를 함께 갱신한다.

## 2. 확정 아키텍처

```text
고객 앱 ─POST→ 공개 Cloud Run relay ─저장→ Firestore relay_orders
POS 서버 ─GET/PATCH + X-Relay-Token→ relay
Jetson ─GET/PATCH + X-Relay-Token→ relay
Jetson 얼굴인식 UID → APP 활성 주문 조회 → ROS 픽업 안내
```

- 주문의 단일 원본은 기존 `/api/v1/orders` HTTP 계약이다.
- 고객 앱은 Firestore 주문 문서를 직접 만들지 않는다.
- Firestore `relay_orders`는 Cloud Relay의 내부 저장소다.
- 얼굴 프로필은 기존 Firestore `users/{uid}`를 상태·임베딩·선호음료의 기준 원본으로 사용한다.
- Jetson 로컬 `data/face_enrollment/{uid}`가 비어 있어도 Firestore의
  `faceRegistered=true`와 유효한 `faceEmbedding`이 있으면 앱에는 등록 완료로 표시한다.
- 앱의 얼굴 등록 상태와 선호정보는 Firestore `users/{uid}`를 기준으로 관리한다.
- 앱의 `customer_id`, 얼굴인식의 `customer_id`, Firebase Auth `user.uid`는 동일하다.
- 앱은 `EXPO_PUBLIC_API_BASE_URL`에 공개 Cloud Run URL을 사용하므로 Jetson LAN IP가 바뀌어도 주문 생성에 영향이 없다.

## 3. 주문 API v1

### 생성

`POST /api/v1/orders`

```json
{
  "schema_version": "1.0",
  "request_id": "app-...",
  "source": "APP",
  "customer_id": "Firebase UID",
  "items": [{
    "menu_id": 4,
    "menu_name": "레몬에이드",
    "temperature": "ICE",
    "size": "NONE",
    "quantity": 1,
    "options": [],
    "unit_price": 4500
  }],
  "original_text": null,
  "metadata": {"pickup_store": "EWHA_01"}
}
```

응답에는 서버가 계산한 `total_price: 4500`이 포함된다.

- `menu_id`는 `config/menu_catalog.json`의 정수 공식 ID를 사용한다.
- `menu_name`과 `unit_price`는 주문 당시 표시명과 가격의 스냅샷이다.
- 앱/POS가 카탈로그의 현재 이름·가격으로 과거 주문 기록을 덮어쓰지 않는다.
- `total_price`는 요청에서 받지 않고 서버가
  `Σ(unit_price × quantity)`로 계산하여 저장·응답한다.
- 필드명은 기존 통합 API와 동일하게 snake_case를 사용한다. camelCase
  `menuId/menu/unitPrice/totalPrice`를 별도 계약으로 만들지 않는다.

### enum

| 항목 | 값 |
|---|---|
| source | `APP`, `ROBOT`, `POS` |
| status | `RECEIVED`, `PREPARING`, `READY`, `PICKED_UP`, `CANCELLED` |
| temperature | `HOT`, `ICE`, `NONE` |

상태 전이:

```text
RECEIVED → PREPARING → READY → PICKED_UP
RECEIVED/PREPARING → CANCELLED
```

### Jetson/POS 조회

`GET /api/v1/orders?customer_id={uid}&source=APP&limit=20`

헤더: `X-Relay-Token`. Jetson은 `READY > PREPARING > RECEIVED` 순으로 활성 주문 하나를 선택한다. `PICKED_UP/CANCELLED`는 무시한다.

### 앱 상태 조회

`GET /api/v1/public/orders/{order_id}?request_id={request_id}`

고객 앱은 관리자 토큰 없이 자신이 생성할 때 받은 `order_id + request_id` 조합으로 3초마다 상태를 조회한다. `JETSON_RELAY_TOKEN`을 Expo 환경 변수나 브라우저 번들에 넣지 않는다.

### POS 보안 경계

POS 웹 브라우저에서 `X-Relay-Token`을 직접 노출하면 안 된다. POS 브라우저는 항상 서버 측 API route/proxy만 호출하고 Relay 토큰은 POS 서버 프로세스에만 둔다.

2026 한이음 시연/매장 내부 배치에서는 별도 관리자 비밀번호 로그인 없이 POS를 사용할 수 있다. 이 경우 POS Express 서버는 기본적으로 `127.0.0.1`에만 바인딩하고, 같은 장비의 Vite/정적 웹을 통해서만 접근한다. 다른 장비에서 접근해야 해서 `0.0.0.0` 등으로 공개할 경우에는 매장 내부 신뢰 네트워크 또는 별도 프록시 인증/접근제어를 적용한다.

즉 비밀번호 로그인은 필수 계약이 아니지만, 브라우저 번들에 Relay 토큰을 넣거나 브라우저가 Cloud Relay를 직접 호출하는 구현은 금지한다.

## 4. 상태별 동작

| status | 앱 | POS | 얼굴인식 후 로봇 |
|---|---|---|---|
| RECEIVED | 접수 | 제조 시작 | 접수 상태 음성, 방향 동작 없음 |
| PREPARING | 제조중 | 준비 완료 | 제조 중 음성, 방향 동작 없음 |
| READY | 픽업가능 | 수동 픽업 완료 가능 | 실제 품목 음성 + 왼쪽 가리키기/목 회전 → 안내 TTS 종료 후 3초 뒤 자동 `PICKED_UP` |
| PICKED_UP | 완료 | 지난 주문 | 활성 주문에서 제외 |
| CANCELLED | 취소 | 지난 주문 | 활성 주문에서 제외 |

`READY` 주문은 얼굴을 인식했다는 사실만으로 즉시 `PICKED_UP`으로 바꾸지 않는다.
반드시 `preorder_pickup_ready` 안내가 실제로 결정되고 해당 안내 TTS가 `done` 된 뒤 기본 3초를 기다린 후 Jetson이 Relay의 상태 변경 API를 호출한다.

```text
READY 얼굴인식
→ 실제 주문 내용 + 왼쪽 픽업 안내
→ TTS done
→ 3초
→ PATCH /api/v1/orders/{order_id}/status
   {"status":"PICKED_UP"}
→ 앱에서 완료 상태 확인
```

- 자동 완료 PATCH가 실패하면 상태를 추측해서 로컬에서 완료 처리하지 않고 서버의 기존 `READY` 상태를 유지한다.
- POS는 필요 시 `READY → PICKED_UP`을 수동 처리할 수 있는 운영용 fallback을 유지한다.
- 이미 POS에서 `PICKED_UP` 처리된 주문은 활성 주문 조회에서 제외되므로 다시 자동 안내하지 않는다.

## 5. ROS 계약

얼굴 흐름:

```text
/face_recognition_result
→ face_personalization_node
→ Cloud Relay 활성 주문 비동기 조회
→ preorder가 포함된 /customer_context
→ decision_node
```

READY 결정:

```json
{
  "decision": "GUIDE_CUSTOMER",
  "response_key": "preorder_pickup_ready",
  "response_args": {
    "target": "PICKUP",
    "direction": "LEFT",
    "order_id": "order UUID",
    "customer_id": "Firebase UID",
    "customer_name": "a",
    "status": "READY",
    "items": []
  },
  "reason": "recognized_customer_preorder_ready",
  "state": "WAIT_CUSTOMER_EXIT"
}
```

기존 `GUIDE_CUSTOMER/PICKUP/LEFT`를 재사용하므로 face `SMILE`, display `GUIDE_LEFT`, head `TURN_LEFT`, arm `POINT_LEFT`가 실행되고 TTS 종료 후 head가 `CENTER`로 돌아온다.

대표 음성:

```text
a님, 사전 주문하신 아이스 레몬에이드 한 잔이
왼쪽 음료 수령대에 준비되어 있습니다.
```

우선순위:

```text
READY 사전주문 > PREPARING/RECEIVED 상태 > 단골 선호 메뉴 제안 > 일반 주문
```

조회 실패·잘못된 주문·빈 items일 때는 픽업 준비를 추측하지 않고 기존 단골/일반 주문으로 안전하게 돌아간다.

### READY 자동 완료 계약

`face_personalization_node`는 `/decision_result`에서
`GUIDE_CUSTOMER + preorder_pickup_ready`가 실제로 발행된 주문만 자동 완료 대상으로 기억한다.
그 뒤 `/tts/status == done`을 받은 시점부터 기본 3초를 기다리고, 기존 Relay 인증 토큰을 사용해 해당 주문을 `PICKED_UP`으로 변경한다.

이 방식은 얼굴 인식 직후나 첫 인사 TTS 종료 시점에 주문이 너무 일찍 완료되는 것을 방지한다.

## 6. 환경 변수

| 실행 위치 | 변수 | 의미 |
|---|---|---|
| 앱 | `EXPO_PUBLIC_API_BASE_URL` | 공개 Cloud Run 주문 relay URL |
| 앱 | `EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL` | 얼굴 임베딩 Cloud Run 백엔드 URL |
| Cloud Run | `JETSON_RELAY_TOKEN` | Jetson/POS 서버용 비밀 토큰 |
| Jetson | `PUMPKIN_PREORDER_API_URL` | 동일 Cloud Run relay URL |
| Jetson | `PUMPKIN_PREORDER_API_TOKEN` | relay 토큰; 없으면 `JETSON_RELAY_TOKEN` 사용 |
| Jetson | `PUMPKIN_PREORDER_TIMEOUT_SEC` | 조회/상태 변경 제한 시간, 기본 2.5초 |
| Jetson | `PUMPKIN_PREORDER_AUTO_PICKUP_DELAY_SEC` | READY 픽업 안내 TTS 종료 후 자동 `PICKED_UP`까지 대기 시간, 기본 3.0초 |

## 7. 통합 검증 기준

최종 통합에서는 다음 동작을 확인한다.

- 앱 주문 생성 후 `RECEIVED → PREPARING → READY → PICKED_UP` 상태가 동일 주문 ID로 이어지는지 확인한다.
- 얼굴 인식 UID와 Firebase `user.uid`가 같은 고객을 가리키는지 확인한다.
- `READY` 주문만 픽업 위치 안내를 실행하고, 안내 TTS 완료 전에는 `PICKED_UP`으로 변경하지 않는다.
- Relay 조회나 자동 완료가 실패하면 기존 서버 상태를 유지하고 다른 고객의 주문을 추측해 표시하지 않는다.
- Relay 토큰은 Jetson/POS 서버에서만 사용하고 Expo·브라우저 번들에는 포함하지 않는다.
- 얼굴 임베딩 등록은 `EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL`의 Cloud Run 백엔드를 사용한다.

## 8. 변경 기록

| 날짜 | 변경 | 영향 |
|---|---|---|
| 2026-08-14 | 최초 협업 문서 생성 | 앱·POS·Jetson 공통 기준 |
| 2026-08-14 | 저장소 검사 후 Firestore 직접 계약을 기존 통합 주문 API 계약으로 교정 | source/status/필드명 및 보안 경계 통일 |
| 2026-08-14 | 고객별 relay 조회, 앱 공개 상태 조회, 얼굴 주문 우선 처리, READY 픽업 안내 구현 | 앱·Cloud Relay·ROS |
| 2026-08-14 | APP 주문 menu_id를 공식 정수 ID로 정렬하고 가격 스냅샷/서버 합계 규칙 명시 | 앱·POS·주문 API |
| 2026-08-14 | 모바일 주문/얼굴등록 API URL 분리 | Cloud Run 주문과 Jetson 얼굴등록 동시 사용 |
| 2026-08-14 | 얼굴 등록 상태·선호음료 원본을 Firestore users 문서로 통일 | 잘못된 미등록 표시 및 선호음료 불일치 수정 |
| 2026-08-16 | Jetson API와 Firestore 프로필 조회를 독립 처리 | Jetson API가 꺼져도 등록 완료 상태 유지 |
| 2026-08-14 | READY 얼굴 픽업 안내 TTS 종료 후 기본 3초 뒤 Jetson이 자동 `PICKED_UP` 처리하도록 정책·구현 변경 | Jetson·앱 상태·POS 운영 |
| 2026-08-16 | POS 관리자 비밀번호 로그인을 시연/내부 배치 필수 조건에서 제거하고 로컬 기본 바인딩으로 보안 경계 조정 | POS 실행 단순화·Relay 토큰 서버 보관 유지 |
