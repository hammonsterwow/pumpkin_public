# 공통 주문 API v1

Expo 사전 주문과 ROS2 로봇 주문을 동일한 주문 계약으로 수집합니다. POS는 주문을 직접 저장하지 않고 이 API에서 조회하고 상태만 변경합니다.

## 구조

```text
Expo customer-mobile ─ APP ───┐
                              ├─ POST /api/v1/orders ─ OrderService ─ OrderRepository ─ SQLite
ROS2 decision ─────── ROBOT ──┘                                      ↑
                                                                    POS
```

저장소를 PostgreSQL 등으로 교체할 때는 `OrderRepository` 구현만 교체합니다.

## 실행

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

기본 DB 위치는 `data/orders.sqlite3`입니다. 변경하려면 다음 환경변수를 사용합니다.

```bash
export PUMPKIN_ORDER_DB_PATH=/원하는/경로/orders.sqlite3
```

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
  "customer_id": null,
  "items": [
    {
      "menu_id": "americano",
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
    "pickup_store": "EWHA_01"
  }
}
```

동일한 `request_id`로 재전송하면 새 주문을 만들지 않고 기존 주문을 반환합니다.

## POS API

```text
GET   /api/v1/orders
GET   /api/v1/orders/{order_id}
PATCH /api/v1/orders/{order_id}/status
```

상태 전이는 다음만 허용합니다.

```text
RECEIVED → PREPARING → READY → PICKED_UP
     └──────────→ CANCELLED ←──────────┘
```

## Expo 연결

`apps/customer-mobile/.env`:

```env
EXPO_PUBLIC_API_BASE_URL=http://JETSON_LAN_IP:8000
```

API 클라이언트는 `apps/customer-mobile/src/api/orderApi.ts`에 있습니다. 장바구니 확정 함수에서는 다음처럼 사용합니다.

```ts
import { submitAppOrder } from './src/api/orderApi';

const created = await submitAppOrder(cart, null);
```

실제 휴대폰에서 `localhost`는 휴대폰 자신이므로 Jetson 또는 백엔드 PC의 같은 Wi-Fi IP를 넣어야 합니다.

## ROS2 연결

`ros2_ws/src/robot_controller/robot_controller/order_api_client.py`의 `OrderApiClient`를 사용합니다.

```python
client = OrderApiClient()
created = client.submit_confirmed_order(confirmed_order)
```

환경변수:

```bash
export PUMPKIN_ORDER_API_URL=http://127.0.0.1:8000
```

`decision_node`는 DB나 HTTP 형식을 알 필요가 없습니다. 사용자 확인이 끝난 주문만 `ConfirmedOrder`로 변환해 어댑터에 전달합니다.
