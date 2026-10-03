from __future__ import annotations

import uuid
from typing import Any

from .menu_policy import (
    MAX_QUANTITY,
    default_temperature,
    is_temperature_allowed,
    normalize_menu,
    normalize_quantity,
    normalize_temperature,
)

SCHEMA_VERSION = "1.0"
MAX_ORDER_ITEMS = 3


def new_session_id() -> str:
    return str(uuid.uuid4())


def _first_value(raw_item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw_item.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_item(raw_item: dict[str, Any], item_id: int) -> dict[str, Any]:
    raw_menu = _first_value(raw_item, "menu", "menu_name", "drink")
    raw_temperature = _first_value(raw_item, "temperature", "temp")
    raw_quantity = _first_value(raw_item, "quantity", "count", "qty")

    menu = normalize_menu(raw_menu)
    temperature = normalize_temperature(raw_temperature)
    quantity = normalize_quantity(raw_quantity)

    if menu is not None and temperature is None:
        temperature = default_temperature(menu)

    missing_slots: list[str] = []
    validation_errors: list[str] = []

    if raw_menu is not None and menu is None:
        validation_errors.append("unsupported_menu")
    if raw_temperature is not None:
        raw_temperature_label = str(raw_temperature).strip().upper()
        if temperature is None and raw_temperature_label != "NONE":
            validation_errors.append("unsupported_temperature")
    if raw_quantity is not None and quantity is None:
        validation_errors.append(
            f"quantity_must_be_between_1_and_{MAX_QUANTITY}"
        )
    if (
        menu is not None
        and temperature is not None
        and not is_temperature_allowed(menu, temperature)
    ):
        validation_errors.append("unsupported_temperature_for_menu")

    if menu is None:
        missing_slots.append("menu")
    if temperature is None:
        missing_slots.append("temperature")
    if quantity is None:
        missing_slots.append("quantity")

    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": missing_slots,
        "validation_errors": validation_errors,
    }


def extract_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = raw.get("items")
    if not isinstance(candidates, list):
        order = raw.get("order")
        if isinstance(order, dict) and isinstance(order.get("items"), list):
            candidates = order["items"]
        elif isinstance(order, dict) and order:
            candidates = [order]
        else:
            legacy_item = {
                "menu": (
                    raw.get("menu")
                    or raw.get("menu_label")
                    or raw.get("drink")
                    or raw.get("item")
                ),
                "temperature": (
                    raw.get("temperature")
                    or raw.get("temp")
                    or raw.get("temperature_label")
                ),
                "quantity": (
                    raw.get("quantity")
                    or raw.get("count")
                    or raw.get("qty")
                ),
            }
            has_legacy_value = any(
                value is not None
                for value in legacy_item.values()
            )
            candidates = [legacy_item] if has_legacy_value else []

    normalized: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_ORDER_ITEMS]:
        if not isinstance(candidate, dict):
            continue
        item = normalize_item(candidate, len(normalized))
        empty_item = (
            item["menu"] is None
            and item["temperature"] is None
            and item["quantity"] is None
            and not item["validation_errors"]
        )
        if empty_item:
            continue
        normalized.append(item)
    return normalized


def calculate_order_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "INVALID"
    if any(item["validation_errors"] for item in items):
        return "INVALID"
    if any(item["missing_slots"] for item in items):
        return "INCOMPLETE"
    return "VALID"


def build_order_schema(
    *,
    intent: str,
    confidence: float,
    items: list[dict[str, Any]],
    session_id: str,
    needs_reprompt: bool = False,
) -> dict[str, Any]:
    order_status = calculate_order_status(items)
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "intent": intent,
        "confidence": round(float(confidence), 4),
        "items": items,
        "order_status": order_status,
        "needs_reprompt": bool(needs_reprompt or order_status != "VALID"),
    }
