from __future__ import annotations

from typing import Any

from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String

from .decision_node import DecisionNode
from .dialogue_act_resolver import DialogueActResolver
from .order_dialogue_manager import OrderDialogueManager


class OrderHandoffDecisionNode(DecisionNode):
    """Production FSM with explicit item confirmation and customer handoff.

    Customer presence is intentionally session-latched. A camera ``True`` starts
    one customer session, then subsequent presence changes are ignored for the
    entire order. After the customer explicitly finishes the order, the FSM waits
    for a real ``False`` (customer leaves) and only the following ``True`` starts
    the next customer session.

    Confirmation states are also latched. Ordinary speech or an accidental menu
    mention cannot mutate the active order while the robot is waiting for yes/no.
    Only confirmation, an explicit correction, an explicit additional-order act,
    cancel, or restart can move those states.
    """

    ITEM_CONFIRM_STATE = "ITEM_CONFIRM"
    ORDER_FINISH_STATE = "WAIT_NEXT_CUSTOMER"
    WAIT_CUSTOMER_EXIT_STATE = "WAIT_CUSTOMER_EXIT"
    HANDOFF_STATE = ORDER_FINISH_STATE
    CONFIRMATION_STATES = {
        ITEM_CONFIRM_STATE,
        "ORDER_CONFIRM",
        ORDER_FINISH_STATE,
    }
    USER_GESTURE_TOPIC = "/user/head_gesture"
    USER_GESTURES = {"NOD", "SHAKE"}

    def __init__(self) -> None:
        super().__init__()
        self._customer_exit_seen = False
        self.user_gesture_subscription = self.create_subscription(
            String,
            self.USER_GESTURE_TOPIC,
            self.user_head_gesture_callback,
            10,
        )
        self.get_logger().info(
            f"Visual confirmation enabled on {self.USER_GESTURE_TOPIC}"
        )

    def human_presence_callback(self, msg) -> None:
        """Use presence only to enter one session and hand off to the next one."""
        human_present = bool(msg.data)

        if not self.human_presence_initialized:
            self.human_presence_initialized = True
            self.last_human_presence = human_present
            if human_present and self.state == "IDLE":
                self.handle_human_detected()
            return

        # During an active order, camera presence is informational only.
        if self.state != self.WAIT_CUSTOMER_EXIT_STATE:
            if self.state == "IDLE":
                rising_edge = human_present and not self.last_human_presence
                self.last_human_presence = human_present
                if rising_edge:
                    self.handle_human_detected()
                return

            self.last_human_presence = human_present
            return

        # After order completion, require False -> True before greeting next user.
        self.last_human_presence = human_present
        if not self._customer_exit_seen:
            if not human_present:
                self._customer_exit_seen = True
                self.get_logger().info(
                    "Completed customer left camera view; waiting for next customer."
                )
            return

        if not human_present:
            return

        self._customer_exit_seen = False
        self.state = "IDLE"
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.get_logger().info(
            "New customer detected after completed customer exit. Starting session."
        )
        self.handle_human_detected()

    def _ensure_components(self) -> None:
        """Support lightweight __new__-based unit tests and legacy subclasses."""
        if not hasattr(self, "dialogue_act_resolver"):
            self.dialogue_act_resolver = DialogueActResolver()
        if not hasattr(self, "order_manager"):
            self.order_manager = OrderDialogueManager(
                slot_priority=self.SLOT_PRIORITY,
                group_shared_slots=self.GROUP_SHARED_SLOTS,
            )

    def reprompt_slot(self, nlu_result, reason):
        """Repeat the active slot question without ever discarding partial order state."""
        self.slot_retry_count += 1
        response_key, response_args = self.response_for_waiting()
        return self.reprompt(
            nlu_result,
            reason,
            response_key,
            response_args=response_args,
        )

    def reprompt_nlu(
        self,
        nlu_result,
        reason,
        response_key="nlu_reprompt",
        response_args=None,
    ):
        """Repeat the current prompt indefinitely while preserving the active order."""
        self.nlu_reprompt_count += 1
        return self.reprompt(
            nlu_result,
            reason,
            response_key,
            response_args=response_args,
        )

    def _implicit_confirmation_correction_items(
        self,
        nlu_result: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        """Return a safe same-item correction spoken during ORDER_CONFIRM.

        Users often correct a summary by simply restating the item, for example
        ``아이스 아메리카노 두 잔이요`` after the robot asked whether one cup
        was correct. Requiring a literal word such as ``수정`` or ``바꿔`` makes
        that natural correction impossible.

        At the same time, live microphone audio can contain unrelated chatter with
        a bare quantity (for example ``...한 잔...``). To avoid mutating the order
        from that noise, this implicit path is deliberately narrow: the utterance
        must explicitly name exactly one menu already present in the current order,
        and it must explicitly change quantity or temperature for that same item.
        """
        if self.state != "ORDER_CONFIRM" or self.current_order is None:
            return None

        explicit_slots = nlu_result.get("explicit_slots")
        if not isinstance(explicit_slots, dict):
            return None

        explicit_menus = explicit_slots.get("menus")
        if not isinstance(explicit_menus, list):
            explicit_menus = []
        explicit_menus = [str(menu) for menu in explicit_menus if menu]
        if len(explicit_menus) != 1:
            return None

        incoming_items = self.extract_incoming_items(
            nlu_result,
            prefer_explicit=True,
        )
        if len(incoming_items) != 1:
            return None

        incoming = incoming_items[0]
        incoming_menu = incoming.get("menu")
        if not incoming_menu or incoming_menu != explicit_menus[0]:
            return None

        current_items = self.current_order.get("items", [])
        matching_items = [
            item
            for item in current_items
            if isinstance(item, dict) and item.get("menu") == incoming_menu
        ]
        if len(matching_items) != 1:
            return None

        target = matching_items[0]
        changes_existing_slot = any(
            incoming.get(slot) is not None
            and incoming.get(slot) != target.get(slot)
            for slot in ("quantity", "temperature")
        )
        if not changes_existing_slot:
            return None

        return incoming_items

    def make_user_gesture_decision(self, gesture: str) -> dict[str, Any] | None:
        """Map customer NOD/SHAKE to the same state handlers as spoken yes/no."""
        normalized = str(gesture or "").strip().upper()
        if normalized not in self.USER_GESTURES:
            return None
        if self.state not in self.CONFIRMATION_STATES:
            return None

        synthetic_input: dict[str, Any] = {
            "text": "",
            "intent": "AFFIRM" if normalized == "NOD" else "DENY",
            "confidence": 1.0,
            "needs_reprompt": False,
            "order_status": "NONE",
            "items": [],
            "input_modality": "VISION_GESTURE",
            "user_gesture": normalized,
        }

        if normalized == "NOD":
            decision = self.handle_affirm_intent(synthetic_input)
        else:
            decision = self.handle_deny_intent(synthetic_input)

        decision["input_modality"] = "VISION_GESTURE"
        decision["user_gesture"] = normalized
        return decision

    def user_head_gesture_callback(self, msg: String) -> None:
        gesture = msg.data.strip().upper()
        decision = self.make_user_gesture_decision(gesture)
        if decision is None:
            if gesture in self.USER_GESTURES:
                self.get_logger().info(
                    "Ignoring user head gesture outside confirmation state: "
                    f"gesture={gesture}, state={self.state}"
                )
            return

        self.get_logger().info(
            "Accepted visual confirmation: "
            f"gesture={gesture}, decision={decision.get('decision')}"
        )
        self.publish_decision(decision)

    def _location_guide_resume_prompt(self):
        if self.state == self.ITEM_CONFIRM_STATE and self.current_order is not None:
            response_args = (
                self.response_args_for_waiting(
                    self.waiting_for,
                    self.current_order.get("items", []),
                )
                if self.waiting_for
                else {}
            )
            return {
                "decision": "CONFIRM_ITEM",
                "response_key": "confirm_item",
                "response_args": response_args,
            }
        if self.state == self.ORDER_FINISH_STATE and self.current_order is not None:
            return {
                "decision": "ORDER_CONFIRMED",
                "response_key": "ask_next_customer",
                "response_args": {},
            }
        return super()._location_guide_resume_prompt()

    def make_decision(self, nlu_result):
        """Apply correction handling and guard yes/no confirmation states."""
        self._ensure_components()

        command = self.dialogue_act_resolver.resolve_command(nlu_result)
        confirmation = self.detect_confirmation_intent(nlu_result)

        # Location questions are valid even in guarded yes/no states. Preserve
        # the active confirmation and repeat it after the guide response.
        if command is None:
            guide_decision = self.make_location_guide_decision(nlu_result)
            if guide_decision is not None:
                return guide_decision

        if self.current_order is not None:
            intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
            correction_context = self.state == "ORDER_CORRECTION"
            correction_request = self.dialogue_act_resolver.is_correction_request(
                nlu_result,
                correction_context=correction_context,
            )

            # Corrections are allowed only in states where editing is meaningful.
            correction_allowed = self.state in {
                "ORDER_CORRECTION",
                "ORDER_CONFIRM",
                self.ITEM_CONFIRM_STATE,
            }
            if correction_request and correction_allowed:
                incoming_items = self.extract_incoming_items(
                    nlu_result,
                    prefer_explicit=True,
                )
                if self.has_slot_values(incoming_items):
                    self.reset_retry_counts()
                    return self.handle_order_intent(
                        nlu_result,
                        incoming_items=incoming_items,
                        overwrite=True,
                    )

                if intent == "MODIFY" and not correction_context:
                    return self.request_correction(nlu_result, "modify_detected")

            # A natural correction may omit words such as "수정" or "바꿔".
            # Accept it only when the user explicitly repeats exactly one menu that
            # already exists and changes that item's quantity or temperature.
            if (
                self.state == "ORDER_CONFIRM"
                and command is None
                and confirmation is None
            ):
                incoming_items = self._implicit_confirmation_correction_items(
                    nlu_result
                )
                if incoming_items is not None:
                    self.reset_retry_counts()
                    return self.handle_order_intent(
                        nlu_result,
                        incoming_items=incoming_items,
                        overwrite=True,
                    )

        # While a yes/no answer is expected, arbitrary ORDER predictions must not
        # append items. This prevents surrounding conversation such as a menu name
        # from silently changing an already-confirmed order.
        if (
            self.state in self.CONFIRMATION_STATES
            and command is None
            and confirmation is None
        ):
            return self._repeat_current_confirmation(nlu_result)

        decision = super().make_decision(nlu_result)
        return self._maybe_confirm_item_before_quantity(decision)

    def _repeat_current_confirmation(self, nlu_result):
        if self.state == self.ITEM_CONFIRM_STATE:
            if self.current_order is None:
                return self.reprompt_nlu(
                    nlu_result,
                    "item_confirm_without_order",
                    response_key="affirm_without_order",
                )
            response_args = self.response_args_for_waiting(
                self.waiting_for,
                self.current_order.get("items", []),
            ) if self.waiting_for else {}
            return self.order_decision(
                "CONFIRM_ITEM",
                "confirm_item",
                "confirmation_required",
                self.current_order,
                nlu_result,
                response_args=response_args,
            )

        if self.state == "ORDER_CONFIRM" and self.current_order is not None:
            return self.order_decision(
                "CONFIRM_ORDER",
                "confirm_order",
                "confirmation_required",
                self.current_order,
                nlu_result,
            )

        if self.state == self.ORDER_FINISH_STATE and self.current_order is not None:
            return self.order_decision(
                "ORDER_CONFIRMED",
                "ask_next_customer",
                "finish_confirmation_required",
                self.current_order,
                nlu_result,
            )

        return self.reprompt_nlu(nlu_result, "confirmation_required")

    def _maybe_confirm_item_before_quantity(
        self,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """Turn a single-item quantity question into a separate item confirmation.

        When the NLU has already grounded multiple drinks, confirming only the
        first incomplete item makes the dialogue sound as if the later drinks were
        dropped. Multi-item orders therefore keep the normal slot-collection flow:
        ask the first missing quantity, then the next one, and only confirm the
        complete order after every item is filled. The legacy CONFIRM_ITEM step is
        retained for a single tentative drink.
        """
        if decision.get("decision") != "ASK_QUANTITY":
            return decision
        if decision.get("reason") != "missing_quantity":
            return decision

        order = decision.get("order")
        waiting_for = decision.get("waiting_for")
        if not isinstance(order, dict) or not isinstance(waiting_for, dict):
            return decision

        item_id = waiting_for.get("item_id")
        items = order.get("items", [])
        grounded_items = [item for item in items if isinstance(item, dict)]
        if len(grounded_items) > 1:
            return decision

        target = next(
            (
                item
                for index, item in enumerate(items)
                if isinstance(item, dict)
                and item.get("item_id", index) == item_id
            ),
            None,
        )
        if not isinstance(target, dict):
            return decision
        if not target.get("menu") or target.get("temperature") not in {"ICE", "HOT"}:
            return decision
        if target.get("quantity") is not None:
            return decision

        self.state = self.ITEM_CONFIRM_STATE
        decision["decision"] = "CONFIRM_ITEM"
        decision["response_key"] = "confirm_item"
        decision["reason"] = "confirm_item_before_quantity"
        decision["state"] = self.ITEM_CONFIRM_STATE
        return decision

    def _quantity_question_after_item_affirm(
        self,
        nlu_result: dict[str, Any],
    ) -> dict[str, Any]:
        if self.current_order is None or self.waiting_for is None:
            return self.reprompt_nlu(
                nlu_result,
                "item_confirm_without_order",
                response_key="affirm_without_order",
            )

        self.state = "ASK_QUANTITY"
        self.reset_retry_counts()
        return {
            **self.order_decision(
                "ASK_QUANTITY",
                "ask_quantity",
                "item_confirmed",
                self.current_order,
                nlu_result,
                response_args=self.response_args_for_waiting(
                    self.waiting_for,
                    self.current_order.get("items", []),
                ),
            ),
            "waiting_for": dict(self.waiting_for),
            "missing_item_id": self.waiting_for.get("item_id"),
            "missing_slot": "quantity",
        }

    def handle_affirm_intent(self, nlu_result):
        self._ensure_components()

        if self.state == self.ITEM_CONFIRM_STATE:
            return self._quantity_question_after_item_affirm(nlu_result)

        if self.state == self.ORDER_FINISH_STATE:
            previous_session_id = self.session_id
            self.current_order = None
            self.waiting_for = None
            self.reset_retry_counts()
            self.state = self.WAIT_CUSTOMER_EXIT_STATE
            self._customer_exit_seen = not bool(
                getattr(self, "last_human_presence", True)
            )
            decision = self.simple_decision(
                "NEXT_CUSTOMER_READY",
                "next_customer_ready",
                "order_finished",
                nlu_result,
            )
            decision["previous_session_id"] = previous_session_id
            decision["next_state"] = self.WAIT_CUSTOMER_EXIT_STATE
            decision["semantic_state"] = self.WAIT_CUSTOMER_EXIT_STATE
            decision["semantic_event"] = "ORDER_FINISHED"
            return decision

        if self.state != "ORDER_CONFIRM" or self.current_order is None:
            return self.reprompt_nlu(
                nlu_result,
                "affirm_without_order_confirm",
                response_key="affirm_without_order",
            )

        confirmed_order = self.current_order
        self.state = self.ORDER_FINISH_STATE
        decision = self.order_decision(
            "ORDER_CONFIRMED",
            "ask_next_customer",
            "order_summary_affirmed",
            confirmed_order,
            nlu_result,
        )
        decision["next_state"] = self.ORDER_FINISH_STATE
        decision["semantic_state"] = "WAIT_ORDER_FINISH"
        decision["semantic_response_key"] = "ask_finish_order"

        self.waiting_for = None
        self.reset_retry_counts()
        return decision

    def handle_deny_intent(self, nlu_result):
        self._ensure_components()

        if self.state == self.ITEM_CONFIRM_STATE:
            self.current_order = None
            self.waiting_for = None
            self.reset_retry_counts()
            self.state = "ORDER_LISTEN"
            return self.simple_decision(
                "REORDER_REQUEST",
                "ask_order",
                "item_confirmation_denied",
                nlu_result,
            )

        if self.state == self.ORDER_FINISH_STATE:
            self.waiting_for = None
            self.reset_retry_counts()
            self.state = "ORDER_LISTEN"
            decision = self.simple_decision(
                "CONTINUE_ORDER",
                "continue_order",
                "additional_order_requested",
                nlu_result,
            )
            decision["next_state"] = "ORDER_LISTEN"
            return decision

        if (
            self.state == "ORDER_CONFIRM"
            and self.dialogue_act_resolver.is_additional_order_request(nlu_result)
        ):
            self.waiting_for = None
            self.reset_retry_counts()
            self.state = "ORDER_LISTEN"
            decision = self.simple_decision(
                "CONTINUE_ORDER",
                "continue_order",
                "additional_order_requested_before_confirmation",
                nlu_result,
            )
            decision["next_state"] = "ORDER_LISTEN"
            return decision

        return super().handle_deny_intent(nlu_result)

    def detect_confirmation_intent(self, nlu_result):
        self._ensure_components()
        return self.dialogue_act_resolver.resolve_confirmation(
            nlu_result,
            state=self.state,
            confirmation_states=self.CONFIRMATION_STATES,
            additional_order_as_deny=self.state == "ORDER_CONFIRM",
        )

    def is_additional_order_request(self, nlu_result):
        """Compatibility wrapper for existing tests and callers."""
        self._ensure_components()
        return self.dialogue_act_resolver.is_additional_order_request(nlu_result)


def main(args=None):
    import rclpy

    rclpy.init(args=args)
    node = OrderHandoffDecisionNode()
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
