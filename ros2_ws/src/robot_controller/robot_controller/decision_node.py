import json
import time
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from .dialogue_act_resolver import DialogueActResolver
from .dialogue_slots import recover_live_quantity_answer
from .order_dialogue_manager import OrderDialogueManager
from .order_schema import new_session_id


# Compatibility defaults are class attributes so lightweight tests and legacy
# subclasses that construct DecisionNode with __new__ still receive the same
# delegated behavior without running the ROS constructor.
_DEFAULT_DIALOGUE_ACT_RESOLVER = DialogueActResolver()
_DEFAULT_ORDER_DIALOGUE_MANAGER = OrderDialogueManager()


class DecisionNode(Node):
    """ROS adapter and finite-state controller for the order dialogue.

    Responsibilities kept here:
    - ROS subscriptions and publications
    - FSM transitions
    - session and retry lifecycle
    - human-presence and TTS completion events
    - selection of structured decision/response keys

    Text-level dialogue-act interpretation is delegated to
    :class:`DialogueActResolver`. Order item extraction, merging and missing-slot
    calculations are delegated to :class:`OrderDialogueManager`.

    Compatibility methods such as ``detect_text_command``,
    ``merge_order_items`` and ``next_missing_target`` remain available so
    existing subclasses and tests keep working.
    """

    # Fill one item completely before moving to the next item.
    SLOT_PRIORITY = ("menu", "quantity", "temperature")
    SLOT_STATES = {
        "menu": "ASK_MENU",
        "quantity": "ASK_QUANTITY",
        "temperature": "ASK_TEMPERATURE",
    }
    CORRECTION_STATES = {"ORDER_CONFIRM", "ORDER_CORRECTION"}
    GROUP_SHARED_SLOTS = ("quantity", "temperature")

    dialogue_act_resolver = _DEFAULT_DIALOGUE_ACT_RESOLVER
    order_manager = _DEFAULT_ORDER_DIALOGUE_MANAGER

    def __init__(self):
        super().__init__("decision_node")
        self.declare_parameter("max_nlu_reprompts", 2)
        self.declare_parameter("max_slot_retries", 2)
        self.declare_parameter("tts_status_topic", "/tts/status")

        self.max_nlu_reprompts = int(
            self.get_parameter("max_nlu_reprompts").value
        )
        self.max_slot_retries = int(
            self.get_parameter("max_slot_retries").value
        )

        self.dialogue_act_resolver = DialogueActResolver()
        self.order_manager = OrderDialogueManager(
            slot_priority=self.SLOT_PRIORITY,
            group_shared_slots=self.GROUP_SHARED_SLOTS,
        )

        self.state = "IDLE"
        self.session_id = new_session_id()
        self.current_order: dict[str, Any] | None = None
        self.waiting_for: dict[str, Any] | None = None
        self.nlu_reprompt_count = 0
        self.slot_retry_count = 0

        self.pending_customer_context: dict[str, Any] | None = None
        self.personalized_customer_id: str | None = None
        self.greeting_tts_completed = False

        self.human_presence_initialized = False
        self.last_human_presence = False
        self.last_greeting_time = 0.0
        self.greeting_cooldown_sec = 5.0

        self.create_subscription(String, "/intent_result", self.intent_callback, 10)
        self.create_subscription(
            String,
            "/customer_context",
            self.customer_context_callback,
            10,
        )
        self.create_subscription(
            Bool,
            "/human_presence",
            self.human_presence_callback,
            10,
        )
        self.create_subscription(
            String,
            str(self.get_parameter("tts_status_topic").value),
            self.tts_status_callback,
            10,
        )
        self.publisher = self.create_publisher(String, "/decision_result", 10)
        self.stt_trigger_publisher = self.create_publisher(
            String, "/stt/trigger", 10
        )
        self.get_logger().info("Decision Node started")

    # ------------------------------------------------------------------
    # ROS and lifecycle events
    # ------------------------------------------------------------------
    def human_presence_callback(self, msg):
        human_present = msg.data
        if not self.human_presence_initialized:
            self.human_presence_initialized = True
            self.last_human_presence = human_present
            if human_present:
                self.handle_human_detected()
            return

        if human_present and not self.last_human_presence:
            self.handle_human_detected()
        elif not human_present and self.last_human_presence:
            active_states = {
                "ORDER_CONFIRM",
                "ORDER_CORRECTION",
                "ASK_MENU",
                "ASK_TEMPERATURE",
                "ASK_QUANTITY",
                "ORDER_SUBMITTING",
                "ORDER_COMPLETE",
                # Production order-handoff node uses this legacy external value.
                "WAIT_NEXT_CUSTOMER",
            }
            if self.state not in active_states:
                self.reset_session()
        self.last_human_presence = human_present

    def tts_status_callback(self, msg):
        status = msg.data.strip()
        if status == "done" and self.state == "ORDER_COMPLETE":
            self.get_logger().info("Order completion TTS finished. Resetting dialogue.")
            self.reset_session()
            return
        if status == "done" and self.state == "ORDER_LISTEN":
            self.greeting_tts_completed = True
            self.maybe_offer_preferred_order()

    def customer_context_callback(self, msg):
        try:
            context = json.loads(msg.data)
        except json.JSONDecodeError as error:
            self.get_logger().warning(f"Invalid customer context JSON: {error}")
            return
        if not isinstance(context, dict) or not context.get("recognized"):
            return
        self.pending_customer_context = context
        self.maybe_offer_preferred_order()

    def maybe_offer_preferred_order(self):
        context = self.pending_customer_context
        if (
            not isinstance(context, dict)
            or not self.greeting_tts_completed
            or self.state != "ORDER_LISTEN"
            or not self.last_human_presence
        ):
            return
        if self.maybe_handle_preorder(context):
            return

        customer_id = str(context.get("customer_id") or "").strip()
        menu = str(context.get("preferred_menu") or "").strip()
        temperature = str(
            context.get("preferred_temperature") or "NONE"
        ).upper()
        try:
            quantity = int(context.get("preferred_quantity") or 1)
        except (TypeError, ValueError):
            quantity = 0

        if (
            not customer_id
            or customer_id == self.personalized_customer_id
            or not menu
            or quantity < 1
        ):
            return

        nlu_result = {
            "intent": "ORDER",
            "confidence": 1.0,
            "text": "",
            "session_id": self.session_id,
            "items": [{
                "item_id": 0,
                "menu": menu,
                "temperature": None if temperature == "NONE" else temperature,
                "quantity": quantity,
            }],
        }
        decision = self.handle_order_intent(nlu_result)
        if decision.get("decision") != "CONFIRM_ORDER":
            self.get_logger().warning(
                "Stored preference is not a complete valid order; "
                "continuing ordinary dialogue."
            )
            return

        decision["response_key"] = "preferred_order_offer"
        decision["response_args"] = {
            "name": str(context.get("name") or "").strip(),
            "menu": menu,
            "temperature": temperature,
            "quantity": quantity,
        }
        decision["reason"] = "recognized_customer_preference"
        self.personalized_customer_id = customer_id
        self.pending_customer_context = None

        # START_ORDER normally opens the microphone as soon as its TTS ends.
        # Recognition completes during that same greeting, so cancel that stale
        # listen turn before speaking the personalized confirmation.
        cancel = String()
        cancel.data = "cancel"
        self.stt_trigger_publisher.publish(cancel)
        self.publish_decision(decision)

    def maybe_handle_preorder(self, context):
        order = context.get("preorder") if isinstance(context, dict) else None
        if not isinstance(order, dict):
            return False
        status = str(order.get("status") or "").upper()
        items = [item for item in order.get("items", []) if isinstance(item, dict)]
        customer_id = str(context.get("customer_id") or "").strip()
        order_id = str(order.get("order_id") or "").strip()
        if (
            status not in {"RECEIVED", "PREPARING", "READY"}
            or not items or not customer_id or not order_id
        ):
            return False
        response_key = "preorder_pickup_ready" if status == "READY" else "preorder_status"
        decision_name = "GUIDE_CUSTOMER" if status == "READY" else "PREORDER_STATUS"
        self.personalized_customer_id = customer_id
        self.pending_customer_context = None
        self.state = "WAIT_CUSTOMER_EXIT"
        cancel = String()
        cancel.data = "cancel"
        self.stt_trigger_publisher.publish(cancel)
        self.publish_decision({
            "decision": decision_name,
            "response_key": response_key,
            "response_args": {
                "target": "PICKUP",
                "direction": "LEFT",
                "order_id": order_id,
                "customer_id": customer_id,
                "customer_name": str(context.get("name") or "").strip(),
                "status": status,
                "items": items,
            },
            "reason": f"recognized_customer_preorder_{status.lower()}",
            "state": self.state,
            "session_id": self.session_id,
        })
        return True

    def handle_human_detected(self):
        now = time.time()
        cooldown_active = now - self.last_greeting_time < self.greeting_cooldown_sec
        if self.state != "IDLE" or cooldown_active:
            return

        self.session_id = new_session_id()
        self.state = "GREETING"
        self.pending_customer_context = None
        self.personalized_customer_id = None
        self.greeting_tts_completed = False
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.last_greeting_time = now
        self.publish_decision({
            "decision": "START_ORDER",
            "response_key": "start_order",
            "response_args": {},
            "reason": "human_detected",
            "state": self.state,
            "next_state": "ORDER_LISTEN",
            "session_id": self.session_id,
        })
        self.state = "ORDER_LISTEN"

    def intent_callback(self, msg):
        try:
            nlu_result = json.loads(msg.data)
        except json.JSONDecodeError as error:
            self.get_logger().error(f"Invalid NLU JSON: {error}")
            return
        self.publish_decision(self.make_decision(nlu_result))

    def publish_decision(self, decision):
        ros_msg = String()
        ros_msg.data = json.dumps(decision, ensure_ascii=False)
        self.publisher.publish(ros_msg)
        self.get_logger().info(f"Published decision: {ros_msg.data}")

    # ------------------------------------------------------------------
    # FSM routing
    # ------------------------------------------------------------------
    def make_location_guide_decision(self, nlu_result):
        """Answer a location side-question, then repeat the interrupted prompt."""

        intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
        try:
            confidence = float(nlu_result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if (
            intent != "GUIDE"
            or confidence < 0.75
            or bool(nlu_result.get("needs_reprompt", False))
        ):
            return None

        resume_prompt = self._location_guide_resume_prompt()
        decision = self.simple_decision(
            "GUIDE_CUSTOMER",
            "guide_customer",
            "guide_detected_during_order",
            nlu_result,
            response_args={"direction": nlu_result.get("direction")},
        )
        if resume_prompt is not None:
            decision["resume_prompt"] = resume_prompt
        return decision

    def _location_guide_resume_prompt(self):
        """Describe the exact prompt that should resume after store guidance."""

        response_key = None
        response_args = {}
        resume_decision = None

        if self.state in self.SLOT_STATES.values():
            response_key, response_args = self.response_for_waiting()
            resume_decision = self.state
        elif self.state == "ORDER_CONFIRM" and self.current_order is not None:
            response_key = "confirm_order"
            resume_decision = "CONFIRM_ORDER"
        elif self.state == "ORDER_CORRECTION" and self.current_order is not None:
            response_key = "modify_order"
            resume_decision = "MODIFY_ORDER"
        elif self.state in {"ORDER_LISTEN", "GREETING"}:
            response_key = "ask_order"
            resume_decision = "ASK_ORDER"

        if response_key is None:
            return None
        return {
            "decision": resume_decision,
            "response_key": response_key,
            "response_args": dict(response_args or {}),
        }

    def recover_contextual_slot_answer(self, nlu_result):
        """Ground narrow live-ASR artifacts only in the matching slot state."""

        if (
            self.state != "ASK_QUANTITY"
            or not isinstance(self.waiting_for, dict)
            or self.waiting_for.get("slot") != "quantity"
        ):
            return nlu_result

        explicit_slots = nlu_result.get("explicit_slots")
        if (
            isinstance(explicit_slots, dict)
            and explicit_slots.get("quantity") is not None
        ):
            return nlu_result

        quantity = recover_live_quantity_answer(nlu_result.get("text", ""))
        if quantity is None:
            return nlu_result

        recovered = dict(nlu_result)
        recovered_slots = (
            dict(explicit_slots)
            if isinstance(explicit_slots, dict)
            else {}
        )
        recovered_slots.update({
            "menu": None,
            "menus": [],
            "temperature": None,
            "quantity": quantity,
        })
        recovered["explicit_slots"] = recovered_slots
        recovered["contextual_slot_recovery"] = {
            "slot": "quantity",
            "quantity": quantity,
            "source_text": str(nlu_result.get("text", "")),
        }
        return recovered

    def make_decision(self, nlu_result):
        nlu_result = self.recover_contextual_slot_answer(nlu_result)
        command = self.detect_text_command(nlu_result)
        if command == "CANCEL":
            return self.handle_cancel(nlu_result)
        if command == "RESTART":
            return self.handle_restart(nlu_result)

        intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
        confidence = float(nlu_result.get("confidence", 0.0))
        needs_reprompt = bool(nlu_result.get("needs_reprompt", False))
        order_status = str(nlu_result.get("order_status", "")).upper()

        guide_decision = self.make_location_guide_decision(nlu_result)
        if guide_decision is not None:
            return guide_decision

        collecting_slot = self.state in self.SLOT_STATES.values()
        incoming_items = self.extract_incoming_items(
            nlu_result,
            prefer_explicit=collecting_slot,
        )
        has_slots = self.has_slot_values(incoming_items)

        # A customer should not have to say "아니요" before correcting an order.
        # While confirming (or after a bare denial), any utterance that contains
        # explicit order information is treated as a correction immediately.
        # Parsed from->to menu replacements keep their exact target even when a
        # multi-item order is being edited.
        if (
            self.state in self.CORRECTION_STATES
            and self.current_order is not None
            and has_slots
        ):
            explicit_slots = nlu_result.get("explicit_slots")
            corrected_items = self.apply_explicit_correction(explicit_slots)
            if corrected_items is not None:
                self.slot_retry_count = 0
                return self.handle_order_intent(
                    nlu_result,
                    incoming_items=corrected_items,
                    overwrite=True,
                    replace_items=True,
                )

            correction = (
                explicit_slots.get("correction")
                if isinstance(explicit_slots, dict)
                else None
            )
            if isinstance(correction, dict) and len(self.current_order.get("items", [])) > 1:
                return self.request_correction(
                    nlu_result,
                    "ambiguous_correction_target",
                    response_key="ask_correction_target",
                )

            self.slot_retry_count = 0
            return self.handle_order_intent(
                nlu_result,
                incoming_items=incoming_items,
                overwrite=True,
            )

        # Confirmation is intentionally resolved after direct correction routing.
        # This lets phrases such as "아니요, 바닐라라떼요" update the order instead
        # of being reduced to a bare denial.
        confirmation = self.detect_confirmation_intent(nlu_result)
        if confirmation == "AFFIRM":
            return self.handle_affirm_intent(nlu_result)
        if confirmation == "DENY":
            return self.handle_deny_intent(nlu_result)

        if intent == "MODIFY":
            if self.current_order is not None:
                return self.request_correction(nlu_result, "modify_detected")
            self.state = "ORDER_LISTEN"
            return self.simple_decision(
                "MODIFY_ORDER",
                "modify_without_order",
                "modify_without_order",
                nlu_result,
            )

        # While waiting for one slot, dialogue context takes precedence over the
        # standalone intent score. Explicit short answers such as "따뜻하게요"
        # are routed to the exact item_id stored in waiting_for. A learned CANCEL
        # prediction cannot discard that stronger state-aware slot evidence.
        if collecting_slot:
            if self.should_apply_explicit_to_all(nlu_result):
                self.slot_retry_count = 0
                return self.handle_group_slot_answer(nlu_result)
            if has_slots:
                self.slot_retry_count = 0
                return self.handle_order_intent(
                    nlu_result,
                    incoming_items=incoming_items,
                )
            return self.reprompt_slot(nlu_result, "missing_slot_answer")

        # A first utterance may be short ("라떼요"). If any slot evidence exists,
        # let the order flow ask for the remaining values. Literal cancel commands
        # were already handled above, so model-only CANCEL does not override a
        # clearly grounded order slot here either.
        if self.state in {"ORDER_LISTEN", "GREETING"} and has_slots:
            if intent not in {"GUIDE", "PAYMENT"}:
                return self.handle_order_intent(
                    nlu_result,
                    incoming_items=incoming_items,
                )

        # Learned CANCEL is advisory only. Actual order cancellation requires a
        # literal cancel command resolved from the user's text (handled at the top
        # of this method). This prevents low- or high-confidence model-only CANCEL
        # predictions from wiping an active order because ordinary negative words
        # such as "안 돼" appeared in a noisy STT transcript.
        if intent == "CANCEL":
            return self.reprompt_nlu(
                nlu_result,
                "cancel_without_explicit_command",
            )

        if intent == "ORDER":
            if confidence < 0.75 and order_status != "INCOMPLETE":
                return self.reprompt_nlu(nlu_result, "low_confidence")
            if needs_reprompt and order_status not in {"INCOMPLETE", "INVALID"}:
                return self.reprompt_nlu(nlu_result, "nlu_requested_reprompt")
            return self.handle_order_intent(
                nlu_result,
                incoming_items=incoming_items,
            )

        if confidence < 0.75 or needs_reprompt:
            return self.reprompt_nlu(nlu_result, "low_confidence")

        if intent == "AFFIRM":
            return self.handle_affirm_intent(nlu_result)
        if intent == "DENY":
            return self.handle_deny_intent(nlu_result)
        if intent == "GUIDE":
            return self.simple_decision(
                "GUIDE_CUSTOMER",
                "guide_customer",
                "guide_detected",
                nlu_result,
                response_args={"direction": nlu_result.get("direction")},
            )
        if intent == "PAYMENT":
            return self.simple_decision(
                "PAYMENT_GUIDE",
                "payment_guide",
                "payment_detected",
                nlu_result,
            )
        return self.simple_decision(
            "OUT_OF_POLICY",
            "out_of_policy",
            "unknown_intent",
            nlu_result,
        )

    # ------------------------------------------------------------------
    # Order-domain delegation and compatibility wrappers
    # ------------------------------------------------------------------
    def extract_incoming_items(self, nlu_result, prefer_explicit=False):
        return self.order_manager.extract_incoming_items(
            nlu_result,
            prefer_explicit=prefer_explicit,
        )

    def should_apply_explicit_to_all(self, nlu_result):
        return self.order_manager.should_apply_explicit_to_all(nlu_result)

    def apply_explicit_correction(self, explicit_slots):
        current_items = (
            self.current_order.get("items", [])
            if self.current_order is not None
            else []
        )
        return self.order_manager.apply_explicit_correction(
            current_items,
            explicit_slots,
        )

    def handle_group_slot_answer(self, nlu_result):
        if self.current_order is None:
            return self.reprompt_slot(nlu_result, "group_answer_without_order")

        current_items = self.current_order.get("items", [])
        explicit_slots = nlu_result.get("explicit_slots") or {}
        if not current_items:
            return self.reprompt_slot(nlu_result, "group_answer_without_items")

        compact = self.compact_text(nlu_result.get("text", ""))
        if "둘다" in compact and len(current_items) != 2:
            return self.reprompt(
                nlu_result,
                "group_scope_count_mismatch",
                "group_scope_count_mismatch",
            )

        normalized_items = self.order_manager.apply_group_slots(
            current_items,
            explicit_slots,
        )
        return self.handle_order_intent(
            nlu_result,
            incoming_items=normalized_items,
            overwrite=True,
        )

    def handle_order_intent(
        self,
        nlu_result,
        *,
        incoming_items=None,
        overwrite=False,
        replace_items=False,
    ):
        if incoming_items is None:
            incoming_items = self.extract_incoming_items(
                nlu_result,
                prefer_explicit=self.state in self.SLOT_STATES.values(),
            )

        if not incoming_items:
            if overwrite and self.current_order is not None:
                return self.request_correction(
                    nlu_result,
                    "empty_correction",
                    response_key="ask_correction_content",
                )
            return self.reprompt_slot(nlu_result, "empty_order_items")

        current_items = (
            self.current_order.get("items", [])
            if self.current_order is not None
            else []
        )
        if (
            overwrite
            and not replace_items
            and self.correction_target_is_ambiguous(current_items, incoming_items)
        ):
            return self.request_correction(
                nlu_result,
                "ambiguous_correction_target",
                response_key="ask_correction_target",
            )

        if replace_items:
            merged_items = incoming_items
        elif not current_items:
            merged_items = incoming_items
        else:
            merged_items = self.merge_order_items(
                current_items,
                incoming_items,
                overwrite=overwrite,
            )

        order = self.order_manager.build_order(
            nlu_result=nlu_result,
            items=merged_items,
            session_id=self.session_id,
        )
        self.current_order = order
        self.nlu_reprompt_count = 0
        self.state = "SLOT_CHECK"

        if order["order_status"] == "INVALID":
            if overwrite:
                return self.request_correction(
                    nlu_result,
                    "invalid_correction",
                    response_key="invalid_correction",
                )
            self.state = "OUT_OF_POLICY"
            self.current_order = None
            self.waiting_for = None
            return self.order_decision(
                "OUT_OF_POLICY",
                "invalid_order",
                "invalid_order",
                order,
                nlu_result,
            )

        waiting_for = self.next_missing_target(order["items"])
        if waiting_for is not None:
            self.waiting_for = waiting_for
            order["waiting_for"] = dict(waiting_for)
            slot = str(waiting_for["slot"])
            self.state = self.SLOT_STATES[slot]
            return {
                **self.order_decision(
                    self.state,
                    f"ask_{slot}",
                    f"missing_{slot}",
                    order,
                    nlu_result,
                    response_args=self.response_args_for_waiting(
                        waiting_for,
                        order["items"],
                    ),
                ),
                "waiting_for": dict(waiting_for),
                "missing_item_id": waiting_for["item_id"],
                "missing_slot": slot,
            }

        self.waiting_for = None
        order["waiting_for"] = None
        self.state = "ORDER_CONFIRM"
        return self.order_decision(
            "CONFIRM_ORDER",
            "confirm_order",
            "order_corrected" if overwrite else "all_slots_filled",
            order,
            nlu_result,
        )

    def merge_order_items(self, current_items, incoming_items, overwrite=False):
        return self.order_manager.merge_order_items(
            current_items,
            incoming_items,
            waiting_for=self.waiting_for,
            overwrite=overwrite,
        )

    def find_merge_target(self, current_items, incoming, overwrite):
        return self.order_manager.find_merge_target(
            current_items,
            incoming,
            waiting_for=self.waiting_for,
            overwrite=overwrite,
        )

    def correction_target_is_ambiguous(self, current_items, incoming_items):
        return self.order_manager.correction_target_is_ambiguous(
            current_items,
            incoming_items,
        )

    def next_missing_target(self, items):
        return self.order_manager.next_missing_target(items)

    def response_args_for_waiting(self, waiting_for, items):
        return self.order_manager.response_args_for_waiting(waiting_for, items)

    def response_for_waiting(self):
        if self.waiting_for is None:
            return "ask_menu", {}
        items = self.current_order.get("items", []) if self.current_order else []
        slot = str(self.waiting_for.get("slot", "menu"))
        return (
            f"ask_{slot}",
            self.response_args_for_waiting(self.waiting_for, items),
        )

    def has_slot_values(self, items):
        return self.order_manager.has_slot_values(items)

    # ------------------------------------------------------------------
    # Base confirmation, correction and session transitions
    # ------------------------------------------------------------------
    def handle_affirm_intent(self, nlu_result):
        if self.state != "ORDER_CONFIRM" or self.current_order is None:
            return self.reprompt_nlu(
                nlu_result,
                "affirm_without_order_confirm",
                response_key="affirm_without_order",
            )

        confirmed_order = self.current_order
        self.state = "ORDER_SUBMITTING"
        decision = self.order_decision(
            "ORDER_CONFIRMED",
            "order_confirmed",
            "order_affirmed",
            confirmed_order,
            nlu_result,
        )
        decision["next_state"] = "ORDER_COMPLETE"
        self.state = "ORDER_COMPLETE"
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        return decision

    def handle_deny_intent(self, nlu_result):
        if self.state != "ORDER_CONFIRM" or self.current_order is None:
            return self.reprompt_nlu(
                nlu_result,
                "deny_without_order_confirm",
                response_key="deny_without_order",
            )
        return self.request_correction(nlu_result, "order_denied")

    def request_correction(
        self,
        nlu_result,
        reason,
        response_key="modify_order",
        response_args=None,
    ):
        self.state = "ORDER_CORRECTION"
        self.waiting_for = None
        return self.order_decision(
            "MODIFY_ORDER",
            response_key,
            reason,
            self.current_order,
            nlu_result,
            response_args=response_args,
        )

    def handle_restart(self, nlu_result):
        self.session_id = new_session_id()
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.state = "ORDER_LISTEN"
        return self.simple_decision(
            "REORDER_REQUEST",
            "restart_order",
            "restart_requested",
            nlu_result,
        )

    def handle_cancel(self, nlu_result):
        active = self.current_order is not None or self.state not in {
            "IDLE",
            "ORDER_COMPLETE",
        }
        session_id = self.session_id
        self.reset_session()
        return {
            "decision": "CANCEL_ORDER",
            "response_key": "cancel_order" if active else "no_active_order",
            "response_args": {"active": active},
            "reason": "cancel_detected",
            "state": self.state,
            "session_id": session_id,
            "waiting_for": None,
            "nlu_result": nlu_result,
        }

    # These wrappers preserve the old DecisionNode public API while delegating
    # text interpretation to DialogueActResolver.
    def detect_text_command(self, nlu_result):
        return self.dialogue_act_resolver.resolve_command(nlu_result)

    def detect_confirmation_intent(self, nlu_result):
        return self.dialogue_act_resolver.resolve_confirmation(
            nlu_result,
            state=self.state,
            confirmation_states={"ORDER_CONFIRM"},
        )

    @staticmethod
    def compact_text(text):
        return DialogueActResolver.compact_text(text)

    # ------------------------------------------------------------------
    # Structured decision construction and retry policy
    # ------------------------------------------------------------------
    def order_decision(
        self,
        decision,
        response_key,
        reason,
        order,
        nlu_result,
        response_args=None,
    ):
        return {
            "decision": decision,
            "response_key": response_key,
            "response_args": dict(response_args or {}),
            "reason": reason,
            "state": self.state,
            "session_id": self.session_id,
            "waiting_for": self.waiting_for,
            "order": order,
            "nlu_result": nlu_result,
        }

    def reprompt_slot(self, nlu_result, reason):
        self.slot_retry_count += 1
        if self.slot_retry_count > self.max_slot_retries:
            self.current_order = None
            self.waiting_for = None
            self.slot_retry_count = 0
            self.state = "ORDER_LISTEN"
            return self.simple_decision(
                "REORDER_REQUEST",
                "slot_retry_exhausted",
                "slot_retry_exhausted",
                nlu_result,
            )
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
        self.nlu_reprompt_count += 1
        if self.nlu_reprompt_count > self.max_nlu_reprompts:
            self.current_order = None
            self.waiting_for = None
            self.nlu_reprompt_count = 0
            self.state = "ORDER_LISTEN"
            return self.simple_decision(
                "REORDER_REQUEST",
                "nlu_retry_exhausted",
                "nlu_retry_exhausted",
                nlu_result,
            )
        return self.reprompt(
            nlu_result,
            reason,
            response_key,
            response_args=response_args,
        )

    def reprompt(
        self,
        nlu_result,
        reason,
        response_key="nlu_reprompt",
        response_args=None,
    ):
        return self.order_decision(
            "REPROMPT",
            response_key,
            reason,
            self.current_order,
            nlu_result,
            response_args=response_args,
        )

    def simple_decision(
        self,
        decision,
        response_key,
        reason,
        nlu_result,
        response_args=None,
    ):
        return {
            "decision": decision,
            "response_key": response_key,
            "response_args": dict(response_args or {}),
            "reason": reason,
            "state": self.state,
            "session_id": self.session_id,
            "waiting_for": self.waiting_for,
            "nlu_result": nlu_result,
        }

    def reset_retry_counts(self):
        self.nlu_reprompt_count = 0
        self.slot_retry_count = 0

    def reset_session(self):
        self.state = "IDLE"
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.session_id = new_session_id()
        self.pending_customer_context = None
        self.personalized_customer_id = None
        self.greeting_tts_completed = False


def main(args=None):
    rclpy.init(args=args)
    node = DecisionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
