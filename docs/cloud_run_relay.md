# Cloud Run 주문 중계 서버

고객 앱이 외부 네트워크에서 제출한 주문을 Cloud Run이 Firestore에 보관하고,
Jetson이 주기적으로 가져가 처리하는 경계 서비스입니다. Cloud Run에서는 ROS2,
카메라, 로봇 하드웨어를 직접 실행하지 않습니다.

## API

- `POST /api/v1/orders`: 고객 앱 주문 접수. 기존 앱 요청/응답 계약과 호환됩니다.
- `GET /api/v1/orders?status=RECEIVED`: Jetson의 미처리 주문 조회.
- `GET /api/v1/orders/{order_id}`: Jetson의 주문 단건 조회.
- `PATCH /api/v1/orders/{order_id}/status`: Jetson/POS의 처리 상태 변경.
- `GET /health`: Cloud Run 상태 확인.

조회와 상태 변경에는 `X-Relay-Token` 헤더가 필요합니다. 주문 생성은 고객 앱이
사용할 수 있도록 공개하지만 `request_id` 기반 멱등 처리와 Pydantic 검증을 거칩니다.

## Google Cloud 사전 설정

1. `pumpkin` 프로젝트에 Firestore Native 데이터베이스를 생성합니다.
2. Cloud Run 서비스의 리전을 `asia-northeast3`로 선택합니다.
3. 소스 저장소 빌드는 루트의 `/Dockerfile`을 사용합니다.
4. 환경 변수 `JETSON_RELAY_TOKEN`에 충분히 긴 임의 문자열을 설정합니다.
5. 비용 제한을 위해 최대 인스턴스 수를 `1`, 최소 인스턴스 수를 `0`으로 둡니다.

선택 환경 변수:

```text
PUMPKIN_RELAY_COLLECTION=relay_orders
PUMPKIN_CORS_ORIGINS=*
```

`JETSON_RELAY_TOKEN`은 앱 코드나 GitHub에 넣지 않습니다. Cloud Run 환경 변수 또는
Secret Manager에 보관하고 Jetson에도 같은 값을 별도로 설정합니다.

## 호출 예시

```bash
curl "$CLOUD_RUN_URL/api/v1/orders?status=RECEIVED" \
  -H "X-Relay-Token: $JETSON_RELAY_TOKEN"
```

```bash
curl -X PATCH "$CLOUD_RUN_URL/api/v1/orders/ORDER_ID/status" \
  -H "Content-Type: application/json" \
  -H "X-Relay-Token: $JETSON_RELAY_TOKEN" \
  -d '{"status":"PREPARING"}'
```

고객 앱의 `EXPO_PUBLIC_API_BASE_URL`에는 배포 후 발급된 Cloud Run URL을 넣습니다.

## POS 없이 APP 시연 주문 자동 준비

Cloud Run Relay에 `PUMPKIN_AUTO_PREPARE_APP_ORDERS=true`를 설정하고 새 리비전을 배포하면,
그 이후 생성된 APP 주문만 생성 시각을 기준으로 자동 상태를 계산합니다.

- 생성 직후부터 1초 미만: `RECEIVED`
- 1초 이상 6초 미만: `PREPARING`
- 6초 이후: `READY` (얼굴 인식 픽업 대기)
- `PICKED_UP`과 `CANCELLED`는 자동 변경하지 않습니다.
- 이전 주문과 ROBOT/POS 주문에는 적용하지 않습니다.

이 상태는 Relay 조회 및 상태 변경 요청 시 주문 생성 시각으로 계산됩니다. Cloud Run
인스턴스가 0개여도 Jetson의 고객별 주문 조회와 앱의 상태 조회는 올바른 상태를
받으며, `READY → PICKED_UP` 변경도 허용됩니다. 요청이 없는 동안 Firestore
문서 자체가 매초 갱신되는 방식은 아닙니다. 정확한 시각에 DB 변경 이벤트가
필요한 운영 환경이라면 Cloud Tasks 같은 예약 작업이 별도로 필요합니다.

이 옵션은 **시연용 제조 시간 가정**입니다. 실제 음료 제조 완료를 감지하지 않으므로
실제 매장 운영에서는 끄고 POS의 수동 상태 변경을 사용해야 합니다. 기존 POS
DEMO MODE도 켜면 같은 주문에 중복 전환을 시도할 수 있으므로 이 옵션을 켠
시연에서는 POS DEMO MODE를 OFF로 둡니다.
