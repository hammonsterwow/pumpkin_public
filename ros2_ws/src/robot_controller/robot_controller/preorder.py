from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ACTIVE_STATUSES = {"RECEIVED", "PREPARING", "READY"}
STATUS_PRIORITY = {"READY": 3, "PREPARING": 2, "RECEIVED": 1}


@dataclass(frozen=True)
class PreorderLookupResult:
    order: dict[str, Any] | None
    error: str | None = None


@dataclass(frozen=True)
class PreorderUpdateResult:
    order: dict[str, Any] | None
    error: str | None = None


def select_active_preorder(orders: list[dict[str, Any]], customer_id: str) -> dict[str, Any] | None:
    candidates = [
        order for order in orders
        if isinstance(order, dict)
        and order.get("customer_id") == customer_id
        and order.get("source") == "APP"
        and order.get("status") in ACTIVE_STATUSES
        and isinstance(order.get("items"), list)
        and order["items"]
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda order: (
        STATUS_PRIORITY.get(str(order.get("status")), 0),
        str(order.get("created_at") or ""),
    ))


class PreorderApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("PUMPKIN_PREORDER_API_URL", "")).rstrip("/")
        self.token = token if token is not None else os.getenv(
            "PUMPKIN_PREORDER_API_TOKEN", os.getenv("JETSON_RELAY_TOKEN", "")
        )
        self.timeout = float(os.getenv("PUMPKIN_PREORDER_TIMEOUT_SEC", "2.5"))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def lookup(self, customer_id: str) -> PreorderLookupResult:
        if not self.enabled:
            return PreorderLookupResult(None)
        query = urlencode({"customer_id": customer_id, "source": "APP", "limit": 20})
        headers = {"Accept": "application/json"}
        if self.token:
            headers["X-Relay-Token"] = self.token
        try:
            request = Request(f"{self.base_url}/api/v1/orders?{query}", headers=headers)
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                return PreorderLookupResult(None, "invalid_response")
            return PreorderLookupResult(select_active_preorder(payload, customer_id))
        except Exception as error:
            return PreorderLookupResult(None, f"{type(error).__name__}: {error}")

    def update_status(self, order_id: str, status: str) -> PreorderUpdateResult:
        if not self.enabled:
            return PreorderUpdateResult(None, "client_disabled")
        order_id = str(order_id or "").strip()
        status = str(status or "").strip().upper()
        if not order_id or not status:
            return PreorderUpdateResult(None, "invalid_update_request")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["X-Relay-Token"] = self.token
        body = json.dumps({"status": status}).encode("utf-8")

        try:
            request = Request(
                f"{self.base_url}/api/v1/orders/{order_id}/status",
                data=body,
                headers=headers,
                method="PATCH",
            )
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return PreorderUpdateResult(None, "invalid_response")
            return PreorderUpdateResult(payload)
        except Exception as error:
            return PreorderUpdateResult(None, f"{type(error).__name__}: {error}")

    def mark_picked_up(self, order_id: str) -> PreorderUpdateResult:
        return self.update_status(order_id, "PICKED_UP")
