# 공통 주문 API v1

Expo 고객 앱과 ROS2 로봇 주문을 동일한 Cloud Relay 계약으로 수집합니다. POS는 별도 로컬 주문 DB를 만들지 않고 Cloud Relay의 주문을 조회하고 상태를 변경합니다.

## 구조

```text
Expo customer-mobile ─ APP ───┐
                              ├─ POST /api/v1/orders ─ Cloud Run Relay ─ Firestore
ROS2 robot ────────── ROBOT ──┘                                  ↑
                                                                POS
```

현재 구현은 `cloud_relay/main.py`이며, 주문 저장소는 Firestore의 `relay_orders` 컬렉션입니다.

## 주문 생성

```http
POST /api/v1/orders
Idempotency-Key: app-1720000000000-abc123
Content-Type: application/json
```

```json
{
  "schema_version": "1.0",
  "request_id": "app-1720000000000-abc123",
  "source": "APP",
  "customer_id": "firebase-uid",
  "items": [
    {
      "menu_id": 1,
      "menu_name": "아메리카노",
      "temperature": "ICE",
      "size": "NONE",
      "quantity": 1,
      "options": [],
      "unit_price": 3000
    }
  ],
  "original_text": null,
  "metadata": {
    "pickup_store": "HANIUM_01"
  }
}
```

`request_id`는 SHA-256으로 Firestore 문서 ID에 대응되므로 같은 요청을 다시 보내도 새 주문이 중복 생성되지 않습니다. `Idempotency-Key`를 함께 보낼 경우 본문의 `request_id`와 같아야 합니다.

## 주문 조회와 상태 변경

Jetson/POS용 API:

```text
GET   /api/v1/orders
GET   /api/v1/orders/{order_id}
PATCH /api/v1/orders/{order_id}/status
```

이 API들은 서버에 설정된 `JETSON_RELAY_TOKEN`을 `X-Relay-Token` 헤더로 전달해야 합니다.

고객 앱은 자신이 만든 주문의 상태만 다음 공개 조회 API로 확인합니다.

```text
GET /api/v1/public/orders/{order_id}?request_id={request_id}
```

주문 상태 전이는 다음 범위에서만 허용합니다.

```text
RECEIVED → PREPARING → READY → PICKED_UP
    │           │
    └───────────┴────→ CANCELLED
```

## 고객 앱 연결

`apps/customer-mobile/.env`의 `EXPO_PUBLIC_API_BASE_URL`에 Cloud Relay 주소를 설정합니다. 저장소의 공개 클라이언트 기본값은 `apps/customer-mobile/.env.example`에 있습니다.

API 클라이언트는 `apps/customer-mobile/src/api/orderApi.ts`에 있으며, 주문 생성 후 `order_id`와 `request_id`를 사용해 공개 상태 API를 폴링합니다.

## ROS2 연결

로봇 주문은 `ros2_ws/src/robot_controller/robot_controller/order_submission_node.py`가 최종 확정 주문만 전송합니다. Relay 주소와 토큰은 다음 환경변수를 사용합니다.

```bash
export PUMPKIN_PREORDER_API_URL=https://<cloud-run-service>
export JETSON_RELAY_TOKEN=<server-token>
```

`order_submission_node`는 주문 확인 중간 상태를 전송하지 않고, 주문 종료가 확정된 세션의 최종 주문만 Cloud Relay에 제출합니다.

## 배포 및 운영

Cloud Relay의 배포 구조와 확인 명령은 [cloud_run_relay.md](./cloud_run_relay.md)를 참고합니다. 서버 비밀값인 `JETSON_RELAY_TOKEN`은 저장소에 커밋하지 않습니다.
