from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from api.repositories.sqlite_order_repository import SQLiteOrderRepository
from api.routers.faces import router as faces_router
from api.schemas.order import CreateOrderRequest, OrderResponse, UpdateOrderStatusRequest
from api.services.order_service import InvalidOrderStatusTransition, OrderService

router = APIRouter()
router.include_router(faces_router)
_service = OrderService(SQLiteOrderRepository())
ORDER_PREFIX = "/api/v1/orders"


@router.post(ORDER_PREFIX, response_model=OrderResponse, status_code=status.HTTP_201_CREATED, tags=["orders"])
def create_order(
    payload: CreateOrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> OrderResponse:
    if idempotency_key and idempotency_key != payload.request_id:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key와 request_id가 일치하지 않습니다.",
        )
    return _service.create(payload)


@router.get(ORDER_PREFIX, response_model=list[OrderResponse], tags=["orders"])
def list_orders() -> list[OrderResponse]:
    return _service.list()


@router.get(f"{ORDER_PREFIX}/{{order_id}}", response_model=OrderResponse, tags=["orders"])
def get_order(order_id: str) -> OrderResponse:
    order = _service.find(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return order


@router.patch(f"{ORDER_PREFIX}/{{order_id}}/status", response_model=OrderResponse, tags=["orders"])
def update_order_status(
    order_id: str,
    payload: UpdateOrderStatusRequest,
) -> OrderResponse:
    try:
        order = _service.update_status(order_id, payload.status)
    except InvalidOrderStatusTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    if order is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return order
