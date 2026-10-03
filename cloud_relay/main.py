from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from pydantic import BaseModel, Field, field_validator


COLLECTION = os.getenv("PUMPKIN_RELAY_COLLECTION", "relay_orders")
RELAY_TOKEN = os.getenv("JETSON_RELAY_TOKEN", "")
# Demo-only preparation timing lives in Relay so it works without a POS process.
AUTO_PREPARE_APP_ORDERS = os.getenv("PUMPKIN_AUTO_PREPARE_APP_ORDERS", "false").lower() in {"1", "true", "yes"}

app = FastAPI(title="Pumpkin Cloud Relay", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        value.strip()
        for value in os.getenv("PUMPKIN_CORS_ORIGINS", "*").split(",")
        if value.strip()
    ],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-Relay-Token"],
)


class OrderSource(str, Enum):
    APP = "APP"
    ROBOT = "ROBOT"
    POS = "POS"


class OrderStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.RECEIVED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.PICKED_UP},
    OrderStatus.PICKED_UP: set(),
    OrderStatus.CANCELLED: set(),
}


class OrderItemCreate(BaseModel):
    menu_id: int = Field(ge=1)
    menu_name: str = Field(min_length=1, max_length=100)
    temperature: Literal["HOT", "ICE", "NONE"] = "NONE"
    size: Literal["SMALL", "MEDIUM", "LARGE", "NONE"] = "NONE"
    quantity: int = Field(default=1, ge=1, le=99)
    options: list[str] = Field(default_factory=list)
    unit_price: int = Field(default=0, ge=0)


class CreateOrderRequest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: str = Field(min_length=8, max_length=100)
    source: OrderSource
    customer_id: str | None = None
    items: list[OrderItemCreate] = Field(min_length=1)
    original_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("original_text")
    @classmethod
    def normalize_original_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus


class OrderItemResponse(OrderItemCreate):
    id: str


class OrderResponse(BaseModel):
    order_id: str
    order_number: str
    request_id: str
    source: OrderSource
    customer_id: str | None
    status: OrderStatus
    items: list[OrderItemResponse]
    original_text: str | None
    metadata: dict[str, Any]
    total_price: int
    created_at: datetime
    updated_at: datetime


def database() -> firestore.Client:
    return firestore.Client()


def require_jetson_token(x_relay_token: str | None = Header(default=None)) -> None:
    if not RELAY_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="JETSON_RELAY_TOKEN 환경 변수가 설정되지 않았습니다.",
        )
    if x_relay_token is None or not hmac.compare_digest(x_relay_token, RELAY_TOKEN):
        raise HTTPException(status_code=401, detail="유효하지 않은 중계 토큰입니다.")


def request_document_id(request_id: str) -> str:
    return hashlib.sha256(request_id.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def project_auto_status(document: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Derive demo APP preparation from durable creation time, without a worker.

    Every reader sees the same status even when Cloud Run has scaled to zero.
    Manual cancellation and completed pickup are never overwritten.
    """
    if document.get("source") != OrderSource.APP.value or not document.get("auto_prepare"):
        return document
    current = document.get("status")
    if current not in {OrderStatus.RECEIVED.value, OrderStatus.PREPARING.value}:
        return document
    created = document.get("created_at")
    if not isinstance(created, datetime):
        return document
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    elapsed = ((now or utc_now()) - created).total_seconds()
    if elapsed >= 6:
        next_status, changed_at = OrderStatus.READY, created + timedelta(seconds=6)
    elif elapsed >= 1:
        next_status, changed_at = OrderStatus.PREPARING, created + timedelta(seconds=1)
    else:
        return document
    if current == next_status.value:
        return document
    return {**document, "status": next_status.value, "updated_at": changed_at}


def serialize_order(document: dict[str, Any]) -> OrderResponse:
    return OrderResponse.model_validate(project_auto_status(document))


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "pumpkin-cloud-relay", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "firestore"}


@app.post(
    "/api/v1/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    payload: CreateOrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: firestore.Client = Depends(database),
) -> OrderResponse:
    if idempotency_key and idempotency_key != payload.request_id:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key와 request_id가 일치하지 않습니다.",
        )

    reference = db.collection(COLLECTION).document(request_document_id(payload.request_id))
    transaction = db.transaction()

    @firestore.transactional
    def create_once(current_transaction: firestore.Transaction) -> dict[str, Any]:
        snapshot = reference.get(transaction=current_transaction)
        if snapshot.exists:
            existing = snapshot.to_dict()
            if existing is None:
                raise RuntimeError("저장된 주문을 읽지 못했습니다.")
            return existing

        now = utc_now()
        order_id = str(uuid.uuid4())
        document: dict[str, Any] = {
            "order_id": order_id,
            "order_number": f"ORD-{now:%Y%m%d}-{order_id[:8].upper()}",
            "request_id": payload.request_id,
            "source": payload.source.value,
            "customer_id": payload.customer_id,
            "status": OrderStatus.RECEIVED.value,
            "auto_prepare": AUTO_PREPARE_APP_ORDERS and payload.source == OrderSource.APP,
            "items": [
                {"id": str(uuid.uuid4()), **item.model_dump()}
                for item in payload.items
            ],
            "original_text": payload.original_text,
            "metadata": payload.metadata,
            "total_price": sum(item.unit_price * item.quantity for item in payload.items),
            "created_at": now,
            "updated_at": now,
        }
        current_transaction.set(reference, document)
        return document

    return serialize_order(create_once(transaction))


@app.get(
    "/api/v1/orders",
    response_model=list[OrderResponse],
    dependencies=[Depends(require_jetson_token)],
)
def list_orders(
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    customer_id: str | None = Query(default=None),
    source: OrderSource | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: firestore.Client = Depends(database),
) -> list[OrderResponse]:
    query: Any = db.collection(COLLECTION)
    # A single customer equality filter uses Firestore's built-in index. Source
    # and status are filtered in memory to avoid requiring a deployment-time
    # composite index for the Jetson lookup.
    if customer_id:
        query = query.where("customer_id", "==", customer_id)
    snapshots = query.stream()
    orders = [serialize_order(snapshot.to_dict()) for snapshot in snapshots]
    if source is not None:
        orders = [order for order in orders if order.source == source]
    if order_status is not None:
        orders = [order for order in orders if order.status == order_status]
    return sorted(orders, key=lambda order: order.created_at, reverse=True)[:limit]


def find_order_reference(db: firestore.Client, order_id: str) -> Any:
    matches = db.collection(COLLECTION).where("order_id", "==", order_id).limit(1).stream()
    return next(matches, None)


@app.get(
    "/api/v1/orders/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_jetson_token)],
)
def get_order(order_id: str, db: firestore.Client = Depends(database)) -> OrderResponse:
    snapshot = find_order_reference(db, order_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return serialize_order(snapshot.to_dict())


@app.get("/api/v1/public/orders/{order_id}", response_model=OrderResponse)
def get_public_order_status(
    order_id: str,
    request_id: str = Query(min_length=8, max_length=100),
    db: firestore.Client = Depends(database),
) -> OrderResponse:
    """Allow the app to poll only the order it created without exposing admin token."""
    snapshot = find_order_reference(db, order_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    order = serialize_order(snapshot.to_dict())
    if not hmac.compare_digest(order.request_id, request_id):
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return order


@app.patch(
    "/api/v1/orders/{order_id}/status",
    response_model=OrderResponse,
    dependencies=[Depends(require_jetson_token)],
)
def update_order_status(
    order_id: str,
    payload: UpdateOrderStatusRequest,
    db: firestore.Client = Depends(database),
) -> OrderResponse:
    snapshot = find_order_reference(db, order_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    reference = snapshot.reference
    transaction = db.transaction()

    @firestore.transactional
    def update(current_transaction: firestore.Transaction) -> dict[str, Any]:
        current_snapshot = reference.get(transaction=current_transaction)
        document = current_snapshot.to_dict()
        if document is None:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        document = project_auto_status(document)
        current_status = OrderStatus(document["status"])
        if payload.status != current_status and payload.status not in ALLOWED_TRANSITIONS[current_status]:
            raise HTTPException(
                status_code=409,
                detail=f"{current_status.value}에서 {payload.status.value}(으)로 변경할 수 없습니다.",
            )
        document["status"] = payload.status.value
        document["updated_at"] = utc_now()
        current_transaction.set(reference, document)
        return document

    return serialize_order(update(transaction))
