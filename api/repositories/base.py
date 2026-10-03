from __future__ import annotations

from typing import Protocol

from api.schemas.order import CreateOrderRequest, OrderResponse, OrderStatus


class OrderRepository(Protocol):
    def create(self, payload: CreateOrderRequest) -> OrderResponse:
        ...

    def list(self) -> list[OrderResponse]:
        ...

    def find_by_id(self, order_id: str) -> OrderResponse | None:
        ...

    def find_by_request_id(self, request_id: str) -> OrderResponse | None:
        ...

    def update_status(self, order_id: str, status: OrderStatus) -> OrderResponse | None:
        ...
