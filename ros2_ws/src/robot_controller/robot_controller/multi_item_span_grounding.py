from __future__ import annotations

import re
from typing import Any

from .dialogue_slots import extract_explicit_slots
from .menu_policy import QUANTITY_WORDS
from .nlu_postprocess import (
    FUZZY_MENU_MIN_INTENT_CONFIDENCE,
    recover_fuzzy_menu_evidence,
)


_QUANTITY_TOKENS = sorted(QUANTITY_WORDS, key=len, reverse=True)
_QUANTITY_TOKEN_PATTERN = "|".join(
    [r"\d+", *(re.escape(token) for token in _QUANTITY_TOKENS)]
)
_UNIT_QUANTITY_PATTERN = re.compile(
    rf"(?P<number>{_QUANTITY_TOKEN_PATTERN})\s*(?:잔|개|컵)"
)
_ITEM_CONNECTOR_PATTERN = re.compile(r"(?:이랑|랑|하고|그리고|,|과|와)")


def _split_quantity_anchored_item_spans(text: str) -> list[dict[str, Any]]:
    """Split a simple multi-drink utterance into quantity-anchored spans.

    This intentionally handles only the common demo/order form where each drink
    has its own unit-bearing quantity and adjacent drinks are separated by a
    conjunction such as ``이랑``/``하고``/``그리고`` or a comma. Restricting the
    split this way prevents correction phrases such as ``두 잔 말고 한 잔`` from
    being mistaken for two different drinks.
    """

    matches = list(_UNIT_QUANTITY_PATTERN.finditer(text))
    if not 2 <= len(matches) <= 3:
        return []

    for previous, current in zip(matches, matches[1:]):
        between = text[previous.end():current.start()]
        if _ITEM_CONNECTOR_PATTERN.search(between) is None:
            return []

    spans: list[dict[str, Any]] = []
    start = 0
    for index, match in enumerate(matches):
        end = len(text) if index == len(matches) - 1 else match.end()
        span_text = text[start:end].strip()
        if not span_text:
            return []
        spans.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "text": span_text,
                "slots": extract_explicit_slots(span_text),
            }
        )
        start = match.end()
    return spans


def recover_multi_item_span_evidence(
    text: str,
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Recover or preserve a distorted menu inside a simple multi-item order.

    Safety policy:
    - ORDER intent must be very high confidence.
    - The utterance must contain 2-3 quantity-anchored item spans separated by
      ordinary multi-order conjunctions.
    - At least one span must contain an exact supported menu, anchoring the
      sentence as a real multi-item order.
    - Existing correction/group expressions are excluded.
    - A missing menu is fuzzy-recovered only when the corresponding model item
      independently satisfies the existing single-item fuzzy policy.
    - If fuzzy recovery does not pass, the span is preserved as a partial item
      (menu=None) rather than silently deleted. Literal temperature/quantity are
      kept so the dialogue FSM can ask only for the missing menu.

    The raw STT text is never rewritten and the existing fuzzy thresholds are not
    loosened. This helper only emits ``item_hints`` consumed by the established
    explicit-evidence grounding path.
    """

    if not isinstance(explicit_slots, dict):
        return None
    if explicit_slots.get("correction") is not None:
        return None
    if explicit_slots.get("apply_to_all_items"):
        return None
    if str(result.get("intent", "")).upper() != "ORDER":
        return None

    intent_confidence = float(result.get("intent_confidence") or 0.0)
    if intent_confidence < FUZZY_MENU_MIN_INTENT_CONFIDENCE:
        return None

    spans = _split_quantity_anchored_item_spans(text)
    if len(spans) < 2:
        return None

    exact_menu_count = 0
    missing_menu_indexes: list[int] = []
    for span in spans:
        slots = span["slots"]
        if slots.get("quantity") is None:
            return None
        if slots.get("menu") is not None:
            exact_menu_count += 1
        else:
            missing_menu_indexes.append(int(span["index"]))

    # This feature exists specifically for a dropped/distorted menu in an
    # otherwise grounded multi-item order. Do not broaden ordinary exact orders.
    if exact_menu_count == 0 or not missing_menu_indexes:
        return None

    raw_items = result.get("items")
    model_items = (
        [item for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, list)
        else []
    )

    item_hints: list[dict[str, Any]] = []
    fuzzy_recoveries: list[dict[str, Any]] = []
    partial_item_indexes: list[int] = []

    for span in spans:
        index = int(span["index"])
        span_text = str(span["text"])
        span_slots = dict(span["slots"])
        menu = span_slots.get("menu")

        if menu is None and index < len(model_items):
            synthetic_result = {
                "intent": result.get("intent"),
                "intent_confidence": result.get("intent_confidence"),
                "items": [dict(model_items[index])],
            }
            synthetic_slots = dict(span_slots)
            recovery = recover_fuzzy_menu_evidence(
                span_text,
                synthetic_result,
                synthetic_slots,
            )
            if recovery is not None:
                menu = synthetic_slots.get("menu")
                fuzzy_recoveries.append(
                    {
                        "item_index": index,
                        "span_text": span_text,
                        **recovery,
                    }
                )

        if menu is None:
            partial_item_indexes.append(index)

        item_hints.append(
            {
                "menu": menu,
                "temperature": span_slots.get("temperature"),
                "quantity": span_slots.get("quantity"),
            }
        )

    explicit_slots["item_hints"] = item_hints
    return {
        "item_count": len(item_hints),
        "fuzzy_recoveries": fuzzy_recoveries,
        "partial_item_indexes": partial_item_indexes,
        "spans": [
            {
                "index": int(span["index"]),
                "text": str(span["text"]),
                "slots": dict(span["slots"]),
            }
            for span in spans
        ],
    }
