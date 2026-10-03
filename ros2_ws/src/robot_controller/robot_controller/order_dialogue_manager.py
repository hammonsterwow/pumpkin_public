from __future__ import annotations

from typing import Any, Iterable

from .dialogue_slots import has_explicit_slots
from .order_schema import build_order_schema, extract_items


class OrderDialogueManager:
    """Pure order-domain operations used by the dialogue FSM.

    This class does not own ROS subscriptions, FSM state, sessions, retry
    counters, response wording, or hardware actions. DecisionNode passes the
    current context explicitly and remains responsible for state transitions.
    """

    def __init__(
        self,
        *,
        slot_priority: Iterable[str] = ("menu", "quantity", "temperature"),
        group_shared_slots: Iterable[str] = ("quantity", "temperature"),
    ) -> None:
        self.slot_priority = tuple(slot_priority)
        self.group_shared_slots = tuple(group_shared_slots)

    def extract_incoming_items(
        self,
        nlu_result: dict[str, Any],
        *,
        prefer_explicit: bool = False,
    ) -> list[dict[str, Any]]:
        explicit_slots = nlu_result.get("explicit_slots")
        if prefer_explicit and has_explicit_slots(explicit_slots):
            return extract_items({"items": [explicit_slots]})

        model_items = extract_items(nlu_result)
        if model_items:
            return model_items

        if has_explicit_slots(explicit_slots):
            return extract_items({"items": [explicit_slots]})
        return []

    def has_slot_values(self, items: Iterable[dict[str, Any]]) -> bool:
        return any(
            item.get(slot) is not None
            for item in items
            for slot in self.slot_priority
        )

    def should_apply_explicit_to_all(self, nlu_result: dict[str, Any]) -> bool:
        explicit_slots = nlu_result.get("explicit_slots")
        return (
            isinstance(explicit_slots, dict)
            and bool(explicit_slots.get("apply_to_all_items"))
            and any(
                explicit_slots.get(slot) is not None
                for slot in self.group_shared_slots
            )
        )

    def apply_group_slots(
        self,
        current_items: Iterable[dict[str, Any]],
        explicit_slots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        updated_items: list[dict[str, Any]] = []
        for current in current_items:
            updated = dict(current)
            for slot in self.group_shared_slots:
                value = explicit_slots.get(slot)
                if value is not None:
                    updated[slot] = value
            updated_items.append(updated)
        return extract_items({"items": updated_items})

    def apply_explicit_correction(
        self,
        current_items: Iterable[dict[str, Any]],
        explicit_slots: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | None:
        """Apply a parsed ``from -> to`` correction without losing its target.

        Generic overwrite merging is intentionally conservative for multi-item
        orders. A phrase such as ``아메리카노를 딸기스무디로 바꿔`` is not
        ambiguous, however, because the source menu names the exact item. This
        helper preserves that relationship and returns a fully normalized order
        item list. ``None`` means the correction target is still ambiguous.
        """

        if not isinstance(explicit_slots, dict):
            return None
        correction = explicit_slots.get("correction")
        if not isinstance(correction, dict):
            return None
        if str(correction.get("slot", "")) != "menu":
            return None

        target_menu = correction.get("to")
        if not target_menu:
            return None

        updated_items = [dict(item) for item in current_items]
        if not updated_items:
            return None

        source_menu = correction.get("from")
        if source_menu:
            matching_indexes = [
                index
                for index, item in enumerate(updated_items)
                if item.get("menu") == source_menu
            ]
            if len(matching_indexes) != 1:
                return None
            target_index = matching_indexes[0]
        elif len(updated_items) == 1:
            target_index = 0
        else:
            return None

        updated_items[target_index]["menu"] = target_menu
        return extract_items({"items": updated_items})

    def build_order(
        self,
        *,
        nlu_result: dict[str, Any],
        items: list[dict[str, Any]],
        session_id: str,
    ) -> dict[str, Any]:
        order = build_order_schema(
            intent="ORDER",
            confidence=float(nlu_result.get("confidence", 0.0)),
            items=items,
            session_id=str(nlu_result.get("session_id") or session_id),
            needs_reprompt=False,
        )
        order["original_text"] = str(nlu_result.get("text", ""))
        return order

    def merge_order_items(
        self,
        current_items: list[dict[str, Any]],
        incoming_items: list[dict[str, Any]],
        *,
        waiting_for: dict[str, Any] | None,
        overwrite: bool = False,
    ) -> list[dict[str, Any]]:
        if not current_items:
            return incoming_items
        if not incoming_items:
            return current_items

        merged = [dict(item) for item in current_items]
        waiting_item_id = None
        waiting_slot = None
        if waiting_for is not None:
            try:
                waiting_item_id = int(waiting_for.get("item_id", -1))
            except (TypeError, ValueError):
                waiting_item_id = None
            waiting_slot = str(waiting_for.get("slot") or "")

        for incoming in incoming_items:
            target_index = self.find_merge_target(
                merged,
                incoming,
                waiting_for=waiting_for,
                overwrite=overwrite,
            )
            if target_index is None:
                if not overwrite:
                    merged.append(dict(incoming))
                continue

            target = dict(merged[target_index])
            target_item_id = int(target.get("item_id", target_index))
            is_waiting_item = (
                waiting_item_id is not None
                and target_item_id == waiting_item_id
            )

            for slot in self.slot_priority:
                value = incoming.get(slot)
                if value is None:
                    continue
                if overwrite:
                    if slot == "menu" and len(merged) > 1:
                        # In a multi-item correction, an existing menu identifies
                        # the target. It must not rename another item implicitly.
                        if target.get("menu") != value:
                            continue
                    target[slot] = value
                elif target.get(slot) is None:
                    target[slot] = value
                elif is_waiting_item and slot != waiting_slot:
                    # During a slot question, DecisionNode intentionally prefers
                    # explicit text slots over model predictions. If the customer
                    # restates another already-filled field, that restatement is
                    # a correction, not irrelevant context. Example:
                    #   current: 아메리카노 1잔, waiting=temperature
                    #   user: 딸기스무디 스무 잔 주세요
                    # The explicit menu/quantity must replace the stale values;
                    # otherwise the ICE default of 딸기스무디 can be attached to
                    # the old 아메리카노 and produce a phantom order.
                    target[slot] = value

            target["validation_errors"] = list({
                *target.get("validation_errors", []),
                *incoming.get("validation_errors", []),
            })
            merged[target_index] = target

        for item_id, item in enumerate(merged):
            item["item_id"] = item_id
            item["missing_slots"] = [
                slot for slot in self.slot_priority if item.get(slot) is None
            ]
        return merged

    def find_merge_target(
        self,
        current_items: list[dict[str, Any]],
        incoming: dict[str, Any],
        *,
        waiting_for: dict[str, Any] | None,
        overwrite: bool,
    ) -> int | None:
        incoming_menu = incoming.get("menu")
        if incoming_menu:
            for index, item in enumerate(current_items):
                if item.get("menu") == incoming_menu:
                    return index

        if waiting_for is not None:
            item_id = int(waiting_for.get("item_id", -1))
            if 0 <= item_id < len(current_items):
                return item_id

        if overwrite:
            return 0 if len(current_items) == 1 else None

        supplied_slots = [
            slot for slot in self.slot_priority if incoming.get(slot) is not None
        ]
        for index, item in enumerate(current_items):
            if any(item.get(slot) is None for slot in supplied_slots):
                return index
        return None

    @staticmethod
    def correction_target_is_ambiguous(
        current_items: list[dict[str, Any]],
        incoming_items: list[dict[str, Any]],
    ) -> bool:
        if len(current_items) <= 1:
            return False
        current_menus = {
            item.get("menu")
            for item in current_items
            if item.get("menu") is not None
        }
        incoming_menus = {
            item.get("menu")
            for item in incoming_items
            if item.get("menu") is not None
        }
        return not incoming_menus or incoming_menus.isdisjoint(current_menus)

    def next_missing_target(
        self,
        items: Iterable[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for item_index, item in enumerate(items):
            item_id = int(item.get("item_id", item_index))
            for slot in self.slot_priority:
                if item.get(slot) is None:
                    return {"item_id": item_id, "slot": slot}
        return None

    @staticmethod
    def response_args_for_waiting(
        waiting_for: dict[str, Any],
        items: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        item_id = int(waiting_for["item_id"])
        item = next(
            (
                candidate
                for index, candidate in enumerate(items)
                if int(candidate.get("item_id", index)) == item_id
            ),
            {},
        )
        return {
            "item_id": item_id,
            "slot": str(waiting_for["slot"]),
            "menu": item.get("menu"),
        }
