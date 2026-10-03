from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FaceIdentity:
    recognized: bool
    customer_id: str | None
    name: str | None
    similarity: float | None
    threshold: float | None
    reason: str
    preferred_menu: str | None = None
    preferred_temperature: str | None = None
    preferred_quantity: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_quantity(value: Any) -> int | None:
    if value is None:
        return None
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return None
    return quantity if quantity > 0 else None


def parse_face_recognition_payload(payload: str | dict[str, Any]) -> FaceIdentity:
    """Normalize the face-recognition API/ROS payload.

    Invalid, unmatched, or incomplete payloads become a safe anonymous identity
    instead of raising into the ROS callback loop.
    """
    if isinstance(payload, str):
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return FaceIdentity(False, None, None, None, None, "invalid_json")
    elif isinstance(payload, dict):
        raw = payload
    else:
        return FaceIdentity(False, None, None, None, None, "invalid_payload")

    if not isinstance(raw, dict):
        return FaceIdentity(False, None, None, None, None, "invalid_payload")

    matched = bool(raw.get("matched"))
    customer_id = _optional_text(raw.get("customer_id"))
    name = _optional_text(raw.get("name"))
    similarity = _optional_float(raw.get("similarity"))
    threshold = _optional_float(raw.get("threshold"))
    reason = _optional_text(raw.get("reason")) or ("matched" if matched else "unknown")

    if not matched or customer_id is None:
        return FaceIdentity(
            recognized=False,
            customer_id=None,
            name=None,
            similarity=similarity,
            threshold=threshold,
            reason=reason,
        )

    customer = raw.get("customer")
    if not isinstance(customer, dict):
        customer = {}

    return FaceIdentity(
        recognized=True,
        customer_id=customer_id,
        name=name,
        similarity=similarity,
        threshold=threshold,
        reason=reason,
        preferred_menu=_optional_text(
            raw.get("preferred_menu") or customer.get("preferred_menu")
        ),
        preferred_temperature=_optional_text(
            raw.get("preferred_temperature") or customer.get("preferred_temperature")
        ),
        preferred_quantity=_optional_quantity(
            raw.get("preferred_quantity") or customer.get("preferred_quantity")
        ),
    )
