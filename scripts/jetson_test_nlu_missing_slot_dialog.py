#!/usr/bin/env python3
import json
import sys
import time
from collections import deque
from typing import Callable

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class NLUDialogTestNode(Node):
    def __init__(self) -> None:
        super().__init__("nlu_missing_slot_dialog_test")
        self.intent_results: deque[dict] = deque()
        self.decisions: deque[dict] = deque()
        self.actions: deque[dict] = deque()

        self.human_publisher = self.create_publisher(Bool, "/human_presence", 10)
        self.voice_publisher = self.create_publisher(String, "/voice_text", 10)
        self.create_subscription(String, "/intent_result", self._intent_callback, 10)
        self.create_subscription(String, "/decision_result", self._decision_callback, 10)
        self.create_subscription(String, "/robot_action", self._action_callback, 10)

    def _decode(self, payload: str, topic: str) -> dict:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Invalid JSON on {topic}: {error}: {payload}") from error

    def _intent_callback(self, msg: String) -> None:
        result = self._decode(msg.data, "/intent_result")
        self.intent_results.append(result)
        item = self._first_item(result)
        print(
            "[nlu]      "
            f"text={result.get('text')!r} intent={result.get('intent')} "
            f"status={result.get('order_status')} confidence={result.get('confidence')} "
            f"menu={item.get('menu')} temperature={item.get('temperature')} "
            f"quantity={item.get('quantity')}"
        )

    def _decision_callback(self, msg: String) -> None:
        result = self._decode(msg.data, "/decision_result")
        self.decisions.append(result)
        print(
            f"[decision] {result.get('decision')} state={result.get('state')} "
            f"speech={result.get('speech')}"
        )

    def _action_callback(self, msg: String) -> None:
        result = self._decode(msg.data, "/robot_action")
        self.actions.append(result)
        print(
            f"[action]   {result.get('decision')} display={result.get('display')} "
            f"tts={result.get('tts')}"
        )

    @staticmethod
    def _first_item(result: dict) -> dict:
        items = result.get("items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0]
        return {
            "menu": result.get("menu"),
            "temperature": result.get("temperature"),
            "quantity": result.get("quantity"),
        }

    def wait_for_connections(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (
                self.human_publisher.get_subscription_count() >= 1
                and self.voice_publisher.get_subscription_count() >= 1
            ):
                return
        raise TimeoutError("ROS topic subscribers did not connect in time")

    def wait_for(
        self,
        values: deque[dict],
        predicate: Callable[[dict], bool],
        start_index: int,
        label: str,
        timeout: float = 60.0,
    ) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            snapshot = list(values)
            for result in snapshot[start_index:]:
                if predicate(result):
                    return result
        latest = list(values)[-1] if values else None
        raise TimeoutError(f"Timed out waiting for {label}. latest={latest}")

    def publish_human_presence(self, present: bool) -> None:
        msg = Bool()
        msg.data = present
        self.human_publisher.publish(msg)

    def publish_voice_text(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.voice_publisher.publish(msg)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected={expected!r}, actual={actual!r}")


def run_test(node: NLUDialogTestNode) -> None:
    node.wait_for_connections()

    decision_index = len(node.decisions)
    action_index = len(node.actions)
    node.publish_human_presence(False)
    time.sleep(0.3)
    node.publish_human_presence(True)

    node.wait_for(
        node.decisions,
        lambda value: value.get("decision") == "START_ORDER",
        decision_index,
        "START_ORDER decision",
    )
    node.wait_for(
        node.actions,
        lambda value: value.get("decision") == "START_ORDER",
        action_index,
        "START_ORDER action",
    )

    scenarios = [
        ("아메리카노 주세요", "ASK_TEMPERATURE"),
        ("아이스로요", "ASK_QUANTITY"),
        ("두 잔이요", "CONFIRM_ORDER"),
        ("네", "ORDER_CONFIRMED"),
    ]

    confirmation = None
    for utterance, expected_decision in scenarios:
        intent_index = len(node.intent_results)
        decision_index = len(node.decisions)
        action_index = len(node.actions)

        print(f"\n[user]     {utterance}")
        node.publish_voice_text(utterance)

        nlu_result = node.wait_for(
            node.intent_results,
            lambda value, text=utterance: str(value.get("text", "")).strip() == text,
            intent_index,
            f"NLU result for {utterance!r}",
        )
        decision = node.wait_for(
            node.decisions,
            lambda value, expected=expected_decision: value.get("decision") == expected,
            decision_index,
            f"{expected_decision} decision after {utterance!r}",
        )
        node.wait_for(
            node.actions,
            lambda value, expected=expected_decision: value.get("decision") == expected,
            action_index,
            f"{expected_decision} action after {utterance!r}",
        )

        if utterance == "아메리카노 주세요":
            first_item = node._first_item(nlu_result)
            if not first_item.get("menu"):
                raise AssertionError(f"NLU did not extract a menu: {nlu_result}")
        if expected_decision == "CONFIRM_ORDER":
            confirmation = decision

    if confirmation is None:
        raise AssertionError("CONFIRM_ORDER result was not captured")

    order = confirmation.get("order") or {}
    items = order.get("items") or []
    if not items:
        raise AssertionError(f"Confirmed order has no items: {confirmation}")

    item = items[0]
    if not item.get("menu"):
        raise AssertionError(f"Confirmed order menu is missing: {item}")
    assert_equal(item.get("temperature"), "ICE", "confirmed temperature")
    assert_equal(item.get("quantity"), 2, "confirmed quantity")

    print("\n[PASS] Actual NLU -> Decision -> Action missing-slot dialog test passed.")
    print(
        "[ORDER] "
        f"menu={item.get('menu')} temperature={item.get('temperature')} "
        f"quantity={item.get('quantity')}"
    )


def main() -> int:
    rclpy.init()
    node = NLUDialogTestNode()
    try:
        run_test(node)
        return 0
    except Exception as error:
        print(f"\n[FAIL] {error}", file=sys.stderr)
        if node.intent_results:
            print(
                "[LATEST NLU] " + json.dumps(node.intent_results[-1], ensure_ascii=False),
                file=sys.stderr,
            )
        if node.decisions:
            print(
                "[LATEST DECISION] " + json.dumps(node.decisions[-1], ensure_ascii=False),
                file=sys.stderr,
            )
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
