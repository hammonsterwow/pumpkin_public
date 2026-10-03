from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class ConfirmedOrderItem:
    menu_id: int
    menu_name: str
    temperature: str
    quantity: int
    size: str = "NONE"
    options: list[str] = field(default_factory=list)
    unit_price: int = 0


@dataclass(frozen=True)
class ConfirmedOrder:
    items: list[ConfirmedOrderItem]
    original_text: str | None
    confidence: float
    session_id: str
    customer_id: str | None = None
    schema_version: str = "1.0"


class OrderApiClient:
    """Confirmed robot orders -> shared Cloud Relay order contract adapter."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        configured = (
            base_url
            or os.getenv("PUMPKIN_ORDER_API_URL")
            or os.getenv("PUMPKIN_PREORDER_API_URL")
            or os.getenv("POS_RELAY_BASE_URL")
            or "http://127.0.0.1:8000"
        )
        self.base_url = configured.rstrip("/")
        self.timeout = timeout

    def submit_confirmed_order(self, order: ConfirmedOrder) -> dict[str, Any]:
        if not order.items:
            raise ValueError("확정 주문에는 최소 1개의 item이 필요합니다.")

        # One completed customer session must create at most one ROBOT order.
        # Cloud Relay also applies request_id based idempotency, so a retry after
        # a transient network failure cannot duplicate the same robot order.
        request_id = f"robot-{order.session_id}"
        payload = {
            "schema_version": order.schema_version,
            "request_id": request_id,
            "source": "ROBOT",
            "customer_id": order.customer_id,
            "items": [
                {
                    "menu_id": item.menu_id,
                    "menu_name": item.menu_name,
                    "temperature": item.temperature,
                    "size": item.size,
                    "quantity": item.quantity,
                    "options": item.options,
                    "unit_price": item.unit_price,
                }
                for item in order.items
            ],
            "original_text": order.original_text,
            "metadata": {
                "nlu_confidence": order.confidence,
                "session_id": order.session_id,
            },
        }
        return self._post_order(payload)

    def _post_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/api/v1/orders",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": str(payload["request_id"]),
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"주문 API가 {exc.code}을 반환했습니다: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"주문 API에 연결할 수 없습니다: {exc.reason}") from exc
