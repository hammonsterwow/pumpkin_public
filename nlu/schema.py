"""Shared result schema returned by the production NLU predictor."""

from __future__ import annotations

from typing import TypedDict


class ItemConfidence(TypedDict):
    active: float
    menu: float
    temperature: float
    quantity: float


class NLUItem(TypedDict):
    item_id: int
    menu: str | None
    temperature: str | None
    quantity: int | None
    confidence: ItemConfidence
    missing_slots: list[str]


class NLUResult(TypedDict):
    schema_version: str
    model_name: str
    text: str
    intent: str
    intent_confidence: float
    order_status: str
    order_status_confidence: float
    items: list[NLUItem]
    needs_reprompt: bool
    device: str
    latency_ms: float
