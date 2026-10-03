#!/usr/bin/env python3
import json
import time
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class Probe(Node):
    def __init__(self):
        super().__init__("voice_dialog_probe")
        self.voice_pub = self.create_publisher(String, "/voice_text", 10)
        self.presence_pub = self.create_publisher(Bool, "/human_presence", 10)
        self.decisions = deque()
        self.create_subscription(String, "/decision_result", self.on_decision, 10)

    def on_decision(self, msg):
        result = json.loads(msg.data)
        self.decisions.append(result)
        print(result.get("decision"), result.get("speech"))

    def wait_ready(self, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.voice_pub.get_subscription_count() and self.presence_pub.get_subscription_count():
                return
        raise RuntimeError("nlu_node 또는 decision_node를 찾지 못했습니다.")

    def presence(self, value):
        msg = Bool()
        msg.data = value
        self.presence_pub.publish(msg)

    def voice(self, text):
        msg = String()
        msg.data = text
        self.voice_pub.publish(msg)
        print("voice:", text)

    def wait_for(self, expected, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            while self.decisions:
                result = self.decisions.popleft()
                if result.get("decision") == expected:
                    return result
        raise AssertionError(f"Timed out waiting for {expected}")

    def step(self, text, expected):
        self.voice(text)
        return self.wait_for(expected)


def assert_item(result, menu, temperature, quantity):
    items = result["order"]["items"]
    assert len(items) == 1, items
    assert items[0]["menu"] == menu, items[0]
    assert items[0]["temperature"] == temperature, items[0]
    assert items[0]["quantity"] == quantity, items[0]


def assert_items(result, expected):
    items = result["order"]["items"]
    assert len(items) == len(expected), items
    actual = [
        (item["menu"], item["temperature"], item["quantity"])
        for item in items
    ]
    assert actual == expected, actual


def main():
    rclpy.init()
    probe = Probe()
    try:
        probe.wait_ready()
        probe.presence(False)
        time.sleep(0.3)
        probe.presence(True)
        probe.wait_for("START_ORDER")

        result = probe.step("아메리카노 하나요", "ASK_TEMPERATURE")
        assert_item(result, "아메리카노", None, 1)

        result = probe.step("따듯하게요", "CONFIRM_ORDER")
        assert_item(result, "아메리카노", "HOT", 1)

        result = probe.step("네", "ORDER_CONFIRMED")
        assert_item(result, "아메리카노", "HOT", 1)

        assert probe.step("다시 주문할게요", "REORDER_REQUEST")["state"] == "ORDER_LISTEN"

        result = probe.step("딸기스무디하나랑 레모네이드 두개요", "CONFIRM_ORDER")
        assert_items(
            result,
            [
                ("딸기스무디", "ICE", 1),
                ("레몬에이드", "ICE", 2),
            ],
        )

        result = probe.step("네", "ORDER_CONFIRMED")
        assert_items(
            result,
            [
                ("딸기스무디", "ICE", 1),
                ("레몬에이드", "ICE", 2),
            ],
        )

        assert probe.step("취소할게요", "CANCEL_ORDER")["state"] == "IDLE"
        print("[PASS] /voice_text natural dialogue flow")
    finally:
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
