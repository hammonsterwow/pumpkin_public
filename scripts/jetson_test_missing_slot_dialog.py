#!/usr/bin/env python3
import json
import time
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class MissingSlotDialogProbe(Node):
    def __init__(self):
        super().__init__("missing_slot_dialog_probe")
        self.intent_publisher = self.create_publisher(String, "/intent_result", 10)
        self.presence_publisher = self.create_publisher(Bool, "/human_presence", 10)
        self.decisions = deque()
        self.actions = deque()
        self.create_subscription(
            String,
            "/decision_result",
            self.decision_callback,
            10,
        )
        self.create_subscription(
            String,
            "/robot_action",
            self.action_callback,
            10,
        )

    def decision_callback(self, msg):
        payload = json.loads(msg.data)
        self.decisions.append(payload)
        print(
            f"[decision] {payload.get('decision')} "
            f"state={payload.get('state')} speech={payload.get('speech')}"
        )

    def action_callback(self, msg):
        payload = json.loads(msg.data)
        self.actions.append(payload)
        print(
            f"[action]   {payload.get('decision')} "
            f"display={payload.get('display')} tts={payload.get('tts')}"
        )

    def wait_for_discovery(self, timeout_sec=8.0):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            intent_ready = self.intent_publisher.get_subscription_count() > 0
            presence_ready = self.presence_publisher.get_subscription_count() > 0
            if intent_ready and presence_ready:
                return
        raise RuntimeError(
            "decision_node subscriber discovery failed. "
            "Check that decision_node is running."
        )

    def publish_presence(self, present):
        msg = Bool()
        msg.data = present
        self.presence_publisher.publish(msg)

    def publish_intent(self, payload):
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.intent_publisher.publish(msg)

    def wait_for(self, queue, expected_decision, timeout_sec=5.0):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            while queue:
                payload = queue.popleft()
                if payload.get("decision") == expected_decision:
                    return payload
        raise AssertionError(f"Timed out waiting for {expected_decision}")

    def expect_step(self, payload, expected_decision, expected_display):
        self.publish_intent(payload)
        decision = self.wait_for(self.decisions, expected_decision)
        action = self.wait_for(self.actions, expected_decision)
        assert action.get("display") == expected_display, action
        return decision


def assert_item(decision, *, menu, temperature, quantity):
    items = decision["order"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["menu"] == menu, item
    assert item["temperature"] == temperature, item
    assert item["quantity"] == quantity, item


def main():
    rclpy.init()
    probe = MissingSlotDialogProbe()

    try:
        probe.wait_for_discovery()

        # The first presence message initializes the edge detector.
        probe.publish_presence(False)
        time.sleep(0.3)
        probe.publish_presence(True)
        start_decision = probe.wait_for(probe.decisions, "START_ORDER")
        start_action = probe.wait_for(probe.actions, "START_ORDER")
        assert start_decision["next_state"] == "ORDER_LISTEN", start_decision
        assert start_action["display"] == "GREETING", start_action

        ask_temperature = probe.expect_step(
            {
                "schema_version": "1.0",
                "intent": "ORDER",
                "confidence": 0.98,
                "items": [
                    {
                        "menu": "아메리카노",
                        "temperature": None,
                        "quantity": None,
                    }
                ],
                "order_status": "INCOMPLETE",
                "needs_reprompt": True,
                "text": "아메리카노 주세요.",
            },
            "ASK_TEMPERATURE",
            "ASK_TEMPERATURE",
        )
        assert_item(
            ask_temperature,
            menu="아메리카노",
            temperature=None,
            quantity=None,
        )

        ask_quantity = probe.expect_step(
            {
                "schema_version": "1.0",
                "intent": "UNKNOWN",
                "confidence": 0.20,
                "items": [{"temperature": "ICE"}],
                "order_status": "INCOMPLETE",
                "needs_reprompt": True,
                "text": "아이스로요.",
            },
            "ASK_QUANTITY",
            "ASK_QUANTITY",
        )
        assert_item(
            ask_quantity,
            menu="아메리카노",
            temperature="ICE",
            quantity=None,
        )

        confirm_order = probe.expect_step(
            {
                "schema_version": "1.0",
                "intent": "UNKNOWN",
                "confidence": 0.20,
                "items": [{"quantity": 2}],
                "order_status": "INCOMPLETE",
                "needs_reprompt": True,
                "text": "두 잔이요.",
            },
            "CONFIRM_ORDER",
            "ORDER_CONFIRM",
        )
        assert_item(
            confirm_order,
            menu="아메리카노",
            temperature="ICE",
            quantity=2,
        )
        assert confirm_order["speech"] == "아이스 아메리카노 2잔 맞으신가요?"

        confirmed = probe.expect_step(
            {
                "intent": "AFFIRM",
                "confidence": 0.99,
                "needs_reprompt": False,
                "text": "네.",
            },
            "ORDER_CONFIRMED",
            "ORDER_ACCEPTED",
        )
        assert confirmed["state"] == "ORDER_SUBMITTING", confirmed
        assert confirmed["next_state"] == "ORDER_COMPLETE", confirmed
        assert_item(
            confirmed,
            menu="아메리카노",
            temperature="ICE",
            quantity=2,
        )

        print("\n[PASS] Missing-slot dialog state and slot merge test passed.")
    finally:
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
