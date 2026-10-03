from __future__ import annotations

from typing import Any

from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String

from .decision_node_additional_order import AdditionalOrderDecisionNode


class HandQuantityDecisionNode(AdditionalOrderDecisionNode):
    """Production dialogue node with context-gated hand quantity input.

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

    def __init__(self) -> None:
        super().__init__()
        self.user_hand_gesture_subscription = self.create_subscription(
            String,
            self.USER_HAND_GESTURE_TOPIC,
            self.user_hand_gesture_callback,
            10,
        )
        self.get_logger().info(
            f"Hand quantity input enabled on {self.USER_HAND_GESTURE_TOPIC}"
        )

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
