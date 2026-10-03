from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
        cleaned = value.strip()
        return cleaned or None


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
