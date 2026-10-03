from __future__ import annotations

from api.repositories.base import OrderRepository
from api.schemas.order import CreateOrderRequest, OrderResponse, OrderStatus


_ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.RECEIVED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.PICKED_UP},
    OrderStatus.PICKED_UP: set(),
    OrderStatus.CANCELLED: set(),
}


class InvalidOrderStatusTransition(ValueError):
    pass


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    def create(self, payload: CreateOrderRequest) -> OrderResponse:
        return self.repository.create(payload)

    def list(self) -> list[OrderResponse]:
        return self.repository.list()

    def find(self, order_id: str) -> OrderResponse | None:
        return self.repository.find_by_id(order_id)

    def update_status(self, order_id: str, status: OrderStatus) -> OrderResponse | None:
        current = self.repository.find_by_id(order_id)
        if current is None:
            return None

        if status == current.status:
            return current

        if status not in _ALLOWED_TRANSITIONS[current.status]:
            raise InvalidOrderStatusTransition(
                f"{current.status.value}에서 {status.value}(으)로 변경할 수 없습니다."
            )

        return self.repository.update_status(order_id, status)
