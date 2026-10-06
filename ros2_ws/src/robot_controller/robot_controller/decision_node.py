import json
import time
from typing import Any

import rclpy
from rclpy.node import Node

from rclpy.executors import ExternalShutdownException
from std_msgs.msg import Bool, String

from .dialogue_act_resolver import DialogueActResolver
from .dialogue_slots import recover_live_quantity_answer
from .order_dialogue_manager import OrderDialogueManager

from .order_exception_policy import detect_order_exception
from .order_schema import new_session_id


# Defaults used by tests that instantiate the node without __init__.
_DEFAULT_DIALOGUE_ACT_RESOLVER = DialogueActResolver()
_DEFAULT_ORDER_DIALOGUE_MANAGER = OrderDialogueManager()


class _CoreDecisionNode(Node):
    """ROS2 finite-state controller for the order dialogue."""

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

        # Short first utterances with slot evidence enter the normal order flow.
        if self.state in {"ORDER_LISTEN", "GREETING"} and has_slots:
            if intent not in {"GUIDE", "PAYMENT"}:
                return self.handle_order_intent(
                    nlu_result,
                    incoming_items=incoming_items,
                )

        # Only an explicit text command can cancel an active order.
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


class _OrderHandoffMixin:
    """Handle item confirmation and customer handoff."""

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
        """Initialize helpers when tests bypass __init__."""
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
        """Parse a single-item correction during ORDER_CONFIRM."""
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

            # Allow a correction without a correction keyword when one existing item is clear.
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

        # Do not append items while a yes/no confirmation is pending.
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
        """Use item confirmation only for a single tentative item."""
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
        """Keep the existing method name used by callers."""
        self._ensure_components()
        return self.dialogue_act_resolver.is_additional_order_request(nlu_result)


class _AdditionalOrderMixin:
    """Handle additional orders and staged corrections."""

    ADDITIONAL_STATES = {"ORDER_CONFIRM", _OrderHandoffMixin.ORDER_FINISH_STATE}
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

        # Use grounded items so deterministic slot values are preserved.
        incoming_items = self.extract_incoming_items(
            nlu_result,
            prefer_explicit=False,
        )
        if not self.has_slot_values(incoming_items):
            return False, []

        # Additional-order requests must contain a menu.
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

            # Use one-shot replacement when both source and target are explicit.
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


class _HandQuantityMixin:
    """Handle wake-phrase ordering and hand-gesture quantity input."""

    USER_HAND_GESTURE_TOPIC = "/user/hand_gesture"
    HAND_QUANTITY_MAP = {
        "ONE_FINGER": 1,
        "TWO_FINGERS": 2,
        "THREE_FINGERS": 3,
        "FOUR_FINGERS": 4,
        "FIVE_FINGERS": 5,
    }

    WAIT_ORDER_WAKE_STATE = "WAIT_ORDER_WAKE"
    ORDER_WAKE_PHRASE = "주문할게요"
    STT_STATUS_TOPIC = "/stt/status"
    WAKE_RETRY_STT_STATUSES = {
        "no_speech",
        "too_quiet",
        "empty",
        "rejected",
    }

    def __init__(self) -> None:
        super().__init__()
        self.user_hand_gesture_subscription = self.create_subscription(
            String,
            self.USER_HAND_GESTURE_TOPIC,
            self.user_hand_gesture_callback,
            10,
        )
        self.wake_stt_status_subscription = self.create_subscription(
            String,
            self.STT_STATUS_TOPIC,
            self.wake_stt_status_callback,
            10,
        )
        self.get_logger().info(
            f"Hand quantity input enabled on {self.USER_HAND_GESTURE_TOPIC}"
        )
        self.get_logger().info(
            "Order wake gate enabled: human presence arms STT; "
            f"'{self.ORDER_WAKE_PHRASE}' starts the existing order dialogue."
        )

    # ------------------------------------------------------------------
    # Demo-safe order wake gate
    # ------------------------------------------------------------------
    @classmethod
    def _normalize_wake_text(cls, text: object) -> str:
        """Remove spaces/punctuation without broadening the wake phrase."""
        return re.sub(r"[\W_]+", "", str(text or ""), flags=re.UNICODE)

    @classmethod
    def _is_order_wake_phrase(cls, text: object) -> bool:
        return cls._normalize_wake_text(text) == cls.ORDER_WAKE_PHRASE

    def _publish_stt_trigger(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.stt_trigger_publisher.publish(msg)

    def _arm_order_wake_listen(self, *, reason: str) -> None:
        """Start one STT turn only while a detected customer is waiting."""
        if self.state != self.WAIT_ORDER_WAKE_STATE:
            return
        if not bool(getattr(self, "last_human_presence", False)):
            return

        self.get_logger().info(
            "Wake gate listening for "
            f"'{self.ORDER_WAKE_PHRASE}' (reason={reason})."
        )
        self._publish_stt_trigger("listen")

    def _enter_order_wake_gate(self, *, reason: str) -> None:
        """Enter wake-listen mode without starting an order."""
        self.state = self.WAIT_ORDER_WAKE_STATE
        self.current_order = None
        self.waiting_for = None
        self.pending_customer_context = None
        self.personalized_customer_id = None
        self.greeting_tts_completed = False
        self.reset_retry_counts()
        self._customer_exit_seen = False

        self.get_logger().info(
            "Customer present; order dialogue remains idle until "
            f"'{self.ORDER_WAKE_PHRASE}' is recognized (reason={reason})."
        )
        self._arm_order_wake_listen(reason="presence_detected")

    def _leave_order_wake_gate(self) -> None:
        """Cancel wake listening when the detected person leaves."""
        if self.state != self.WAIT_ORDER_WAKE_STATE:
            return

        self._publish_stt_trigger("cancel")
        self.state = "IDLE"
        self.current_order = None
        self.waiting_for = None
        self.pending_customer_context = None
        self.personalized_customer_id = None
        self.greeting_tts_completed = False
        self.reset_retry_counts()
        self.get_logger().info(
            "Customer left before the wake phrase; wake gate reset to IDLE."
        )

    def _start_order_after_wake(self, nlu_result: dict[str, Any]) -> None:
        """Consume the wake phrase, then enter the existing START_ORDER flow once."""
        if self.state != self.WAIT_ORDER_WAKE_STATE:
            return
        if not bool(getattr(self, "last_human_presence", False)):
            self.get_logger().info(
                "Ignoring wake phrase because no customer is currently present."
            )
            return

        pending_context = self.pending_customer_context

        self.get_logger().info(
            "Wake phrase accepted with customer present; starting order dialogue: "
            f"text={nlu_result.get('text', '')!r}"
        )
        self.state = "IDLE"
        self.last_greeting_time = 0.0
        self.handle_human_detected()

        if self.state == "ORDER_LISTEN" and pending_context is not None:
            self.pending_customer_context = pending_context

    def human_presence_callback(self, msg) -> None:
        """Use presence only to arm/cancel wake listening, not to gate a new order."""
        human_present = bool(msg.data)

        if not self.human_presence_initialized:
            self.human_presence_initialized = True
            self.last_human_presence = human_present
            if human_present and self.state == "IDLE":
                self._enter_order_wake_gate(reason="initial_presence")
            return

        self.last_human_presence = human_present

        if self.state == self.WAIT_ORDER_WAKE_STATE:
            if not human_present:
                self._leave_order_wake_gate()
            return

        if self.state == "IDLE" and human_present:
            self._enter_order_wake_gate(reason="presence_available")
            return

        # After a completed order, the same still-present customer may begin a
        # fresh order by saying the wake phrase again. Do not require a
        # human_presence False -> True transition between orders.
        if self.state == self.WAIT_CUSTOMER_EXIT_STATE and human_present:
            self.state = "IDLE"
            self.current_order = None
            self.waiting_for = None
            self.reset_retry_counts()
            self.get_logger().info(
                "Order complete; customer is still present. "
                "Re-arming wake gate without requiring an exit/re-entry."
            )
            self._enter_order_wake_gate(reason="order_complete_customer_present")
            return

    def wake_stt_status_callback(self, msg: String) -> None:
        """Re-arm wake listening when a turn ended without any NLU text."""
        if self.state != self.WAIT_ORDER_WAKE_STATE:
            return
        if not bool(getattr(self, "last_human_presence", False)):
            return

        status = str(msg.data or "").strip().lower()
        if status in self.WAKE_RETRY_STT_STATUSES:
            self._arm_order_wake_listen(reason=f"stt_{status}")

    def intent_callback(self, msg: String) -> None:
        """Consume all pre-order speech unless it is the exact wake phrase."""
        if self.state != self.WAIT_ORDER_WAKE_STATE:
            if self.state == "IDLE" and not bool(
                getattr(self, "last_human_presence", False)
            ):
                self.get_logger().info(
                    "Ignoring NLU result while IDLE because no customer is present."
                )
                return
            super().intent_callback(msg)
            return

        try:
            nlu_result = json.loads(msg.data)
        except json.JSONDecodeError as error:
            self.get_logger().error(f"Invalid NLU JSON while waiting for wake phrase: {error}")
            self._arm_order_wake_listen(reason="invalid_nlu_json")
            return

        text = nlu_result.get("text", "")
        if self._is_order_wake_phrase(text):
            self._start_order_after_wake(nlu_result)
            return

        self.get_logger().info(
            "Ignoring pre-order speech because wake phrase did not match: "
            f"text={text!r}"
        )
        # Stay silent and passive until the exact wake phrase is heard.
        # Background speech from presenters/judges must never reach the normal
        # dialogue/action pipeline while we are only waiting for "주문할게요".
        self._arm_order_wake_listen(reason="non_wake_speech")

    def make_user_hand_gesture_decision(
        self,
        gesture: str,
    ) -> dict[str, Any] | None:
        """Map a hand pose to the active quantity slot."""
        normalized = str(gesture or "").strip().upper()
        quantity = self.HAND_QUANTITY_MAP.get(normalized)
        if quantity is None:
            return None

        if self.state != "ASK_QUANTITY":
            return None
        if not isinstance(self.waiting_for, dict):
            return None
        if self.waiting_for.get("slot") != "quantity":
            return None
        if self.current_order is None:
            return None

        synthetic_input: dict[str, Any] = {
            "text": "",
            "intent": "ORDER",
            "confidence": 1.0,
            "intent_confidence": 1.0,
            "needs_reprompt": False,
            "order_status": "INCOMPLETE",
            "items": [],
            "explicit_slots": {
                "menu": None,
                "menus": [],
                "temperature": None,
                "quantity": quantity,
            },
            "input_modality": "VISION_HAND_GESTURE",
            "user_hand_gesture": normalized,
            "vision_quantity": quantity,
        }

        decision = self.make_decision(synthetic_input)
        decision["input_modality"] = "VISION_HAND_GESTURE"
        decision["user_hand_gesture"] = normalized
        decision["vision_quantity"] = quantity
        return decision

    def user_hand_gesture_callback(self, msg: String) -> None:
        gesture = str(msg.data or "").strip().upper()
        decision = self.make_user_hand_gesture_decision(gesture)
        if decision is None:
            if gesture in self.HAND_QUANTITY_MAP:
                self.get_logger().info(
                    "Ignoring hand quantity gesture outside quantity state: "
                    f"gesture={gesture}, state={self.state}, "
                    f"waiting_for={self.waiting_for}"
                )
            return

        self.get_logger().info(
            "Accepted visual quantity input: "
            f"gesture={gesture}, quantity={decision.get('vision_quantity')}, "
            f"decision={decision.get('decision')}"
        )
        self.publish_decision(decision)


class DecisionNode(
    _HandQuantityMixin,
    _AdditionalOrderMixin,
    _OrderHandoffMixin,
    _CoreDecisionNode,
):
    """Decision node composed from feature mixins."""


def main(args=None):
    rclpy.init(args=args)
    node = DecisionNode()
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
