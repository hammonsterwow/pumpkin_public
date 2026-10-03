from __future__ import annotations

import json
import re
from typing import Any

from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String

from .decision_node_additional_order import AdditionalOrderDecisionNode


class HandQuantityDecisionNode(AdditionalOrderDecisionNode):
    """Production dialogue node with wake-gated ordering and hand quantity input.

    A camera presence event alone no longer starts the order dialogue. Presence
    only arms a narrow wake gate and opens STT. The existing order flow begins
    only after STT/NLU returns the exact wake phrase ``주문할게요`` (ignoring
    whitespace and punctuation) while the customer is still present.

    Hand gestures are intentionally interpreted only while the FSM is waiting
    for a quantity slot. This prevents a casual V-sign elsewhere in the
    conversation from mutating the order.
    """

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
        """Presence arms listening but deliberately does not greet/start an order."""
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

        # Face recognition may finish while the customer waits silently at the
        # wake gate. handle_human_detected() clears pending context because the old
        # flow expected recognition to happen during the greeting, so preserve it
        # across activation and let the existing post-greeting logic consume it.
        pending_context = self.pending_customer_context

        self.get_logger().info(
            "Wake phrase accepted with customer present; starting order dialogue: "
            f"text={nlu_result.get('text', '')!r}"
        )
        self.state = "IDLE"
        # Presence bounce protection is no longer needed here because an explicit
        # wake phrase is now required. Let a valid wake start immediately even if
        # a previous greeting happened less than the legacy 5-second cooldown ago.
        self.last_greeting_time = 0.0
        self.handle_human_detected()

        if self.state == "ORDER_LISTEN" and pending_context is not None:
            self.pending_customer_context = pending_context

    def human_presence_callback(self, msg) -> None:
        """Require presence + wake phrase before starting each customer session."""
        human_present = bool(msg.data)

        if not self.human_presence_initialized:
            self.human_presence_initialized = True
            self.last_human_presence = human_present
            if human_present and self.state == "IDLE":
                self._enter_order_wake_gate(reason="initial_presence")
            return

        if self.state == self.WAIT_ORDER_WAKE_STATE:
            self.last_human_presence = human_present
            if not human_present:
                self._leave_order_wake_gate()
            return

        # During an active order, preserve main's session latch: camera presence
        # is informational and cannot reset or restart the customer's order.
        if self.state != self.WAIT_CUSTOMER_EXIT_STATE:
            if self.state == "IDLE":
                rising_edge = human_present and not self.last_human_presence
                self.last_human_presence = human_present
                if rising_edge:
                    self._enter_order_wake_gate(reason="presence_rising_edge")
                return

            self.last_human_presence = human_present
            return

        # After a completed customer, still require a real exit before the next
        # person can arm the wake phrase. The next True only opens the wake gate;
        # it never greets or starts ordering by itself.
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

        self.state = "IDLE"
        self.current_order = None
        self.waiting_for = None
        self.reset_retry_counts()
        self.get_logger().info(
            "New customer detected after completed customer exit; "
            "arming order wake gate."
        )
        self._enter_order_wake_gate(reason="next_customer_presence")

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
            # A wake capture can already be in NLU when the person walks away.
            # Never let that stale result create an order from IDLE with no person.
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
        self._arm_order_wake_listen(reason="non_wake_speech")

    def make_user_hand_gesture_decision(
        self,
        gesture: str,
    ) -> dict[str, Any] | None:
        """Map a supported hand pose to the active quantity slot.

        The synthetic input follows the same structured slot path used by short
        spoken answers such as "두 잔이요". NLU inference is deliberately
        skipped because vision already produced a structured quantity value.
        """
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


def main(args=None):
    import rclpy

    rclpy.init(args=args)
    node = HandQuantityDecisionNode()
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
