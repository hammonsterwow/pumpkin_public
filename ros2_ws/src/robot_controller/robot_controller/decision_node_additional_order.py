from __future__ import annotations

from typing import Any

from rclpy.executors import ExternalShutdownException

from .decision_node_order_handoff import OrderHandoffDecisionNode
from .order_exception_policy import detect_order_exception


class AdditionalOrderDecisionNode(OrderHandoffDecisionNode):
    """Production order flow with additional-order and staged correction support.

    Additional drinks can still be appended while an order is being confirmed.
    Bare/ambiguous correction requests use a separate two-turn target-selection
    flow so a multi-item order is never modified by guessing which drink the
    customer meant.
    """

    ADDITIONAL_STATES = {"ORDER_CONFIRM", OrderHandoffDecisionNode.ORDER_FINISH_STATE}
    CORRECTION_TARGET_STATE = "ORDER_CORRECTION_TARGET"
    CORRECTION_REPLACEMENT_STATE = "ORDER_CORRECTION_REPLACEMENT"
    ORDER_EXCEPTION_STATES = {
        "GREETING",
        "ORDER_LISTEN",
        "ASK_MENU",
        "ASK_TEMPERATURE",
    }

    def __init__(self) -> None:
        super().__init__()
        self.correction_target_item_id: int | None = None

    @classmethod
    def _looks_like_explicit_addition_text(cls, text: object) -> bool:
        compact = cls.compact_text(text)
        if not compact:
            return False

        # "추가" is an unambiguous dialogue cue in the cafe order domain.
        if "추가" in compact:
            return True

        # Natural variants such as "딸기스무디 두 잔 더 주세요".
        if "더" in compact and any(
            cue in compact
            for cue in (
                "주세요",
                "주문",
                "시켜",
                "시킬",
                "넣어",
                "할게",
                "할래",
            )
        ):
            return True

        return False

    def _is_slot_bearing_additional_order(
        self,
        nlu_result: dict[str, Any],
    ) -> tuple[bool, list[dict[str, Any]]]:
        self._ensure_components()
        if self.state not in self.ADDITIONAL_STATES or self.current_order is None:
            return False, []

        text_addition = self._looks_like_explicit_addition_text(
            nlu_result.get("text", "")
        )
        resolver_addition = self.dialogue_act_resolver.is_additional_order_request(
            nlu_result
        )
        if not text_addition and not resolver_addition:
            return False, []

        # Use grounded/model items rather than explicit_slots only. Some menus have
        # a deterministic temperature (for example a smoothie can already be ICE)
        # that is intentionally absent from explicit text evidence.
        incoming_items = self.extract_incoming_items(
            nlu_result,
            prefer_explicit=False,
        )
        if not self.has_slot_values(incoming_items):
            return False, []

        # Require an actual new order slot. This prevents a bare "추가할게요" from
        # creating an empty phantom item.
        if not any(item.get("menu") for item in incoming_items):
            return False, []

        return True, incoming_items

    def _append_additional_items(
        self,
        nlu_result: dict[str, Any],
        incoming_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current_items = (
            self.current_order.get("items", [])
            if isinstance(self.current_order, dict)
            else []
        )
        combined_items = [dict(item) for item in current_items]
        combined_items.extend(dict(item) for item in incoming_items)

        # Each standalone NLU turn numbers its predicted items from zero again.
        # After appending, reassign IDs across the full order so a missing slot on
        # the new drink cannot accidentally resolve to an older item with item_id=0.
        for item_id, item in enumerate(combined_items):
            item["item_id"] = item_id
            item["missing_slots"] = [
                slot for slot in self.SLOT_PRIORITY if item.get(slot) is None
            ]

        self.waiting_for = None
        self.reset_retry_counts()
        self.state = "ORDER_LISTEN"
        decision = self.handle_order_intent(
            nlu_result,
            incoming_items=combined_items,
            replace_items=True,
        )

        if decision.get("decision") == "CONFIRM_ORDER":
            decision["reason"] = "additional_order_appended"
        return self._maybe_confirm_item_before_quantity(decision)

    # ------------------------------------------------------------------
    # Staged partial-item correction
    # ------------------------------------------------------------------
    def _clear_correction_target(self) -> None:
        self.correction_target_item_id = None

    def _current_items(self) -> list[dict[str, Any]]:
        if not isinstance(self.current_order, dict):
            return []
        return [
            item
            for item in self.current_order.get("items", [])
            if isinstance(item, dict)
        ]

    @staticmethod
    def _has_explicit_from_to_correction(explicit_slots: object) -> bool:
        if not isinstance(explicit_slots, dict):
            return False
        correction = explicit_slots.get("correction")
        if not isinstance(correction, dict):
            return False
        source = correction.get("from")
        target = correction.get("to")
        return source is not None and target is not None and source != target

    @staticmethod
    def _target_criteria(explicit_slots: object) -> dict[str, Any]:
        if not isinstance(explicit_slots, dict):
            return {}
        criteria: dict[str, Any] = {}
        for slot in ("menu", "temperature", "quantity"):
            value = explicit_slots.get(slot)
            if value is not None:
                criteria[slot] = value
        return criteria

    def _matching_correction_targets(
        self,
        nlu_result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        explicit_slots = nlu_result.get("explicit_slots")
        criteria = self._target_criteria(explicit_slots)
        if not criteria:
            return [], {}

        matches: list[dict[str, Any]] = []
        for index, item in enumerate(self._current_items()):
            if any(item.get(slot) != value for slot, value in criteria.items()):
                continue
            candidate = dict(item)
            candidate.setdefault("item_id", index)
            matches.append(candidate)
        return matches, criteria

    def _target_prompt_decision(
        self,
        nlu_result: dict[str, Any],
        *,
        response_key: str,
        reason: str,
        response_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.state = self.CORRECTION_TARGET_STATE
        self.waiting_for = None
        return self.order_decision(
            "MODIFY_ORDER",
            response_key,
            reason,
            self.current_order,
            nlu_result,
            response_args=response_args,
        )

    def _select_correction_target(
        self,
        nlu_result: dict[str, Any],
        matches: list[dict[str, Any]],
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        if not matches:
            return self._target_prompt_decision(
                nlu_result,
                response_key="ask_correction_target_not_found",
                reason="correction_target_not_found",
            )

        if len(matches) > 1:
            return self._target_prompt_decision(
                nlu_result,
                response_key="ask_correction_target_disambiguation",
                reason="correction_target_ambiguous",
                response_args={
                    "requested_menu": criteria.get("menu"),
                    "candidates": [dict(item) for item in matches],
                },
            )

        target = dict(matches[0])
        try:
            target_item_id = int(target.get("item_id", 0))
        except (TypeError, ValueError):
            target_item_id = 0

        self.correction_target_item_id = target_item_id
        self.state = self.CORRECTION_REPLACEMENT_STATE
        self.waiting_for = None
        self.reset_retry_counts()
        return self.order_decision(
            "MODIFY_ORDER",
            "ask_correction_replacement",
            "correction_target_selected",
            self.current_order,
            nlu_result,
            response_args={
                "target_item_id": target_item_id,
                "target_item": target,
            },
        )

    def _handle_correction_target_answer(
        self,
        nlu_result: dict[str, Any],
    ) -> dict[str, Any]:
        matches, criteria = self._matching_correction_targets(nlu_result)
        if not criteria:
            return self._target_prompt_decision(
                nlu_result,
                response_key="ask_correction_target_selection",
                reason="correction_target_missing",
            )
        return self._select_correction_target(nlu_result, matches, criteria)

    def _handle_correction_replacement(
        self,
        nlu_result: dict[str, Any],
    ) -> dict[str, Any]:
        current_items = self._current_items()
        target_item_id = getattr(self, "correction_target_item_id", None)
        if target_item_id is None or not current_items:
            self._clear_correction_target()
            return self._target_prompt_decision(
                nlu_result,
                response_key="ask_correction_target_selection",
                reason="correction_target_lost",
            )

        target_index = next(
            (
                index
                for index, item in enumerate(current_items)
                if int(item.get("item_id", index)) == int(target_item_id)
            ),
            None,
        )
        if target_index is None:
            self._clear_correction_target()
            return self._target_prompt_decision(
                nlu_result,
                response_key="ask_correction_target_selection",
                reason="correction_target_lost",
            )

        incoming_items = self.extract_incoming_items(
            nlu_result,
            prefer_explicit=False,
        )
        replacements = [
            dict(item)
            for item in incoming_items
            if isinstance(item, dict) and item.get("menu")
        ]
        if len(replacements) != 1:
            target = dict(current_items[target_index])
            return self.order_decision(
                "MODIFY_ORDER",
                "ask_correction_replacement",
                "correction_replacement_menu_required",
                self.current_order,
                nlu_result,
                response_args={
                    "target_item_id": target_item_id,
                    "target_item": target,
                },
            )

        replacement = replacements[0]
        replacement["item_id"] = int(target_item_id)

        updated_items = [dict(item) for item in current_items]
        updated_items[target_index] = replacement

        self._clear_correction_target()
        self.waiting_for = None
        self.reset_retry_counts()
        self.state = "ORDER_CORRECTION"
        return self.handle_order_intent(
            nlu_result,
            incoming_items=updated_items,
            overwrite=True,
            replace_items=True,
        )

    def request_correction(
        self,
        nlu_result,
        reason,
        response_key="modify_order",
        response_args=None,
    ):
        """Ask for correction content directly when only one drink can be meant."""
        if self.current_order is None:
            return super().request_correction(
                nlu_result,
                reason,
                response_key=response_key,
                response_args=response_args,
            )

        current_items = self._current_items()
        self._clear_correction_target()
        if len(current_items) == 1:
            return super().request_correction(
                nlu_result,
                reason,
                response_key="ask_correction_content",
                response_args=response_args,
            )

        return self._target_prompt_decision(
            nlu_result,
            response_key="ask_correction_target_selection",
            reason=reason,
        )

    def handle_restart(self, nlu_result):
        self._clear_correction_target()
        return super().handle_restart(nlu_result)

    def handle_cancel(self, nlu_result):
        self._clear_correction_target()
        return super().handle_cancel(nlu_result)

    def _handle_s8_order_exception(
        self,
        nlu_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.state not in self.ORDER_EXCEPTION_STATES:
            return None

        exception = detect_order_exception(
            nlu_result,
            state=self.state,
            current_order=self.current_order,
            waiting_for=self.waiting_for,
        )
        if exception is None:
            return None

        self._clear_correction_target()
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.state = "ORDER_LISTEN"

        kind = str(exception.get("kind") or "")
        if kind == "UNSUPPORTED_TEMPERATURE_FOR_MENU":
            return self.simple_decision(
                "OUT_OF_POLICY",
                "unsupported_temperature_for_menu",
                "unsupported_temperature_for_menu",
                nlu_result,
                response_args={
                    "menu": exception.get("menu"),
                    "temperature": exception.get("temperature"),
                },
            )

        if kind == "UNSUPPORTED_MENU":
            return self.simple_decision(
                "OUT_OF_POLICY",
                "unsupported_menu",
                "unsupported_menu",
                nlu_result,
                response_args={
                    "observed_text": exception.get("observed_text"),
                },
            )
        return None

    def make_decision(self, nlu_result):
        self._ensure_components()
        nlu_result = self.recover_contextual_slot_answer(nlu_result)

        # Cancellation/restart must remain available while the staged correction
        # flow is asking either of its follow-up questions.
        command = self.dialogue_act_resolver.resolve_command(nlu_result)
        if command == "CANCEL":
            return self.handle_cancel(nlu_result)
        if command == "RESTART":
            return self.handle_restart(nlu_result)

        guide_decision = self.make_location_guide_decision(nlu_result)
        if guide_decision is not None:
            return guide_decision

        exception_decision = self._handle_s8_order_exception(nlu_result)
        if exception_decision is not None:
            return exception_decision

        if self.state == self.CORRECTION_TARGET_STATE:
            return self._handle_correction_target_answer(nlu_result)
        if self.state == self.CORRECTION_REPLACEMENT_STATE:
            return self._handle_correction_replacement(nlu_result)

        is_addition, incoming_items = self._is_slot_bearing_additional_order(
            nlu_result
        )
        if is_addition:
            return self._append_additional_items(nlu_result, incoming_items)

        # A phrase such as "아메리카노 바꿀게요" identifies an existing target,
        # but does not yet say what should replace it. If one exact item matches,
        # remember that item and ask for the replacement. If multiple items match
        # (e.g. ICE and HOT Americano), never guess: ask the customer to narrow it.
        if self.current_order is not None and self.state in {
            "ORDER_CONFIRM",
            self.ITEM_CONFIRM_STATE,
        }:
            correction_request = self.dialogue_act_resolver.is_correction_request(
                nlu_result,
                correction_context=False,
            )
            explicit_slots = nlu_result.get("explicit_slots")

            # Preserve the existing one-shot source->replacement path when the
            # customer says both sides explicitly, e.g. "아메리카노를
            # 딸기스무디로 바꿀게요". The staged flow is for requests that only
            # identify a target or are otherwise ambiguous.
            if (
                correction_request
                and self._has_explicit_from_to_correction(explicit_slots)
            ):
                corrected_items = self.apply_explicit_correction(explicit_slots)
                if corrected_items is not None:
                    self.reset_retry_counts()
                    return self.handle_order_intent(
                        nlu_result,
                        incoming_items=corrected_items,
                        overwrite=True,
                        replace_items=True,
                    )

            if (
                correction_request
                and not self._has_explicit_from_to_correction(explicit_slots)
            ):
                matches, criteria = self._matching_correction_targets(nlu_result)
                if criteria and matches:
                    return self._select_correction_target(
                        nlu_result,
                        matches,
                        criteria,
                    )

        return super().make_decision(nlu_result)


def main(args=None):
    import rclpy

    rclpy.init(args=args)
    node = AdditionalOrderDecisionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
