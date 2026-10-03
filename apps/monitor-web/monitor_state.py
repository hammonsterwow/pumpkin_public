from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
MENU_CATALOG_PATH = PROJECT_ROOT / "config" / "menu_catalog.json"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def decode_json_message(message: Any) -> dict[str, Any] | None:
    raw = _clean_text(getattr(message, "data", ""))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return payload if isinstance(payload, dict) else {"raw": payload}


def load_menu_catalog(path: Path = MENU_CATALOG_PATH) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for raw_menu in payload.get("menus", []):
        if not isinstance(raw_menu, dict):
            continue
        menu = dict(raw_menu)
        name = _clean_text(menu.get("name"))
        if not name:
            continue
        candidates = [menu.get("menu_id"), name, *(menu.get("aliases") or [])]
        for candidate in candidates:
            if candidate is None:
                continue
            lookup[_clean_text(candidate).lower()] = menu
    return lookup


MENU_CATALOG = load_menu_catalog()


def display_menu(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    menu = MENU_CATALOG.get(text.lower())
    if isinstance(menu, dict):
        canonical = _clean_text(menu.get("name"))
        if canonical:
            return canonical
    return text


def normalize_display_item(raw: dict[str, Any], fallback_item_id: int) -> dict[str, Any]:
    menu = display_menu(
        raw.get("menu") or raw.get("menu_name") or raw.get("menu_id")
    )

    temperature_raw = _clean_text(raw.get("temperature")).upper()
    temperature = temperature_raw if temperature_raw in {"ICE", "HOT"} else None

    quantity_raw = raw.get("quantity")
    quantity: int | None = None
    if isinstance(quantity_raw, int) and not isinstance(quantity_raw, bool):
        quantity = quantity_raw if quantity_raw > 0 else None
    elif isinstance(quantity_raw, str) and quantity_raw.strip().isdigit():
        parsed = int(quantity_raw.strip())
        quantity = parsed if parsed > 0 else None

    explicit_missing = raw.get("missing_slots")
    missing_slots = (
        [str(slot) for slot in explicit_missing if str(slot) in {"menu", "temperature", "quantity"}]
        if isinstance(explicit_missing, list)
        else []
    )
    for slot, value in (
        ("menu", menu),
        ("temperature", temperature),
        ("quantity", quantity),
    ):
        if value is None and slot not in missing_slots:
            missing_slots.append(slot)

    item_id = raw.get("item_id")
    if not isinstance(item_id, int):
        item_id = fallback_item_id

    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": missing_slots,
    }


def extract_items(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates: Any = payload.get("items")
    order = payload.get("order")
    if isinstance(order, dict) and isinstance(order.get("items"), list):
        candidates = order.get("items")

    if not isinstance(candidates, list):
        return []

    items: list[dict[str, Any]] = []
    for index, raw in enumerate(candidates):
        if not isinstance(raw, dict):
            continue
        item = normalize_display_item(raw, index)
        if (
            item["menu"] is None
            and item["temperature"] is None
            and item["quantity"] is None
        ):
            continue
        items.append(item)
    return items


CLEAR_ORDER_DECISIONS = {
    "START_ORDER",
    "REORDER_REQUEST",
    "CANCEL_ORDER",
}


@dataclass
class MonitorState:
    connected: bool = False
    presence: bool = False
    stt_status: str = ""
    tts_status: str = ""
    user_text: str = ""
    robot_text: str = ""
    decision: str = ""
    decision_state: str = ""
    session_id: str = ""
    waiting_for: dict[str, Any] | None = None
    nlu_items: list[dict[str, Any]] = field(default_factory=list)
    order_items: list[dict[str, Any]] = field(default_factory=list)
    version: int = 0

    def _changed(self) -> None:
        self.version += 1

    def set_connected(self, connected: bool) -> None:
        if self.connected != connected:
            self.connected = connected
            self._changed()

    def update_presence(self, present: bool) -> None:
        if self.presence != present:
            self.presence = present
            self._changed()

    def update_stt_status(self, status: str) -> None:
        status = _clean_text(status)
        if self.stt_status != status:
            self.stt_status = status
            self._changed()

    def update_tts_status(self, status: str) -> None:
        status = _clean_text(status)
        if self.tts_status != status:
            self.tts_status = status
            self._changed()

    def update_user_text(self, text: str) -> None:
        text = _clean_text(text)
        if text and self.user_text != text:
            self.user_text = text
            self._changed()

    def update_robot_text(self, text: str) -> None:
        text = _clean_text(text)
        if text and self.robot_text != text:
            self.robot_text = text
            self._changed()

    def update_nlu(self, payload: dict[str, Any]) -> None:
        items = extract_items(payload)
        if items != self.nlu_items:
            self.nlu_items = items
            self._changed()

    def update_decision(self, payload: dict[str, Any]) -> None:
        decision = _clean_text(payload.get("decision")).upper()
        state = _clean_text(payload.get("state")).upper()
        session_id = _clean_text(payload.get("session_id"))

        new_session = bool(session_id and self.session_id and session_id != self.session_id)
        if new_session:
            self.user_text = ""
            self.robot_text = ""
            self.nlu_items = []
            self.order_items = []

        changed = False
        if decision != self.decision:
            self.decision = decision
            changed = True
        if state != self.decision_state:
            self.decision_state = state
            changed = True
        if session_id and session_id != self.session_id:
            self.session_id = session_id
            changed = True

        waiting_for = payload.get("waiting_for")
        normalized_waiting = dict(waiting_for) if isinstance(waiting_for, dict) else None
        if normalized_waiting != self.waiting_for:
            self.waiting_for = normalized_waiting
            changed = True

        decision_items = extract_items(payload)
        if decision_items:
            if decision_items != self.order_items:
                self.order_items = decision_items
                changed = True
        elif decision in CLEAR_ORDER_DECISIONS:
            if self.order_items or self.nlu_items:
                self.order_items = []
                self.nlu_items = []
                changed = True

        if decision == "START_ORDER":
            if self.user_text or self.robot_text:
                self.user_text = ""
                self.robot_text = ""
                changed = True

        if changed or new_session:
            self._changed()

    def snapshot(self) -> dict[str, Any]:
        # Decision/FSM order is authoritative once it exists. The latest NLU items
        # are only a short-lived preview before Decision publishes the accumulated
        # order. No missing slot is ever filled here.
        items = self.order_items if self.order_items else self.nlu_items
        return {
            "connected": self.connected,
            "presence": self.presence,
            "stt_status": self.stt_status,
            "tts_status": self.tts_status,
            "user_text": self.user_text,
            "robot_text": self.robot_text,
            "decision": self.decision,
            "decision_state": self.decision_state,
            "waiting_for": dict(self.waiting_for) if self.waiting_for else None,
            "items": [dict(item) for item in items],
            "version": self.version,
        }
