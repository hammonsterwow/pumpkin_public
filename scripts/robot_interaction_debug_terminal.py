#!/usr/bin/env python3
"""Concise diagnostic console for the physical Pumpkin demo."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, String


class DemoDebugConsole(Node):
    REQUIRED_PUBLISHERS = {
        "/human_presence": "vision",
        "/stt/status": "STT",
        "/voice_text": "STT text",
        "/intent_result": "NLU",
        "/decision_result": "Decision/FSM",
        "/response_result": "Response",
        "/robot_action": "Action",
        "/tts/status": "TTS",
    }

    def __init__(self) -> None:
        super().__init__("pumpkin_demo_debug_console")
        self._lock = threading.Lock()
        self.turn = 0
        self.last_presence: bool | None = None
        self.last_stt_status = ""
        self.last_tts_status = ""

        self.create_subscription(Bool, "/human_presence", self.on_presence, 10)
        self.create_subscription(String, "/user/head_gesture", self.on_gesture, 10)
        self.create_subscription(String, "/user/hand_gesture", self.on_hand_quantity, 10)
        self.create_subscription(String, "/stt/status", self.on_stt_status, 10)
        self.create_subscription(String, "/voice_text", self.on_voice_text, 10)
        self.create_subscription(String, "/intent_result", self.on_intent, 10)
        self.create_subscription(String, "/decision_result", self.on_decision, 10)
        self.create_subscription(String, "/response_result", self.on_response, 10)
        self.create_subscription(String, "/robot_action", self.on_action, 10)
        self.create_subscription(String, "/tts/status", self.on_tts_status, 10)

    def write(self, tag: str, text: str) -> None:
        with self._lock:
            stamp = time.strftime("%H:%M:%S")
            prefix = f"[{stamp}]"
            if self.turn:
                prefix += f" [TURN {self.turn:02d}]"
            print(f"{prefix} {tag:<10} {text}", flush=True)

    @staticmethod
    def decode(message: String) -> dict[str, Any] | None:
        try:
            value = json.loads(str(message.data))
        except (json.JSONDecodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def compact_items(items: Any) -> str:
        if not isinstance(items, list) or not items:
            return "-"
        out: list[str] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            menu = item.get("menu") or "?"
            temp = item.get("temperature") or "?"
            qty = item.get("quantity")
            qty_text = "?" if qty is None else str(qty)
            out.append(f"#{index} {menu}/{temp}/{qty_text}")
        return "; ".join(out) or "-"

    @staticmethod
    def compact_explicit(explicit: Any) -> str:
        if not isinstance(explicit, dict) or not explicit:
            return "-"
        parts = []
        for key in ("menu", "temperature", "quantity"):
            value = explicit.get(key)
            if value is not None:
                parts.append(f"{key}={value}")
        correction = explicit.get("correction")
        if isinstance(correction, dict) and correction:
            parts.append(f"correction={correction}")
        return ", ".join(parts) or "-"

    def missing(self) -> list[str]:
        return [
            f"{topic} ({owner})"
            for topic, owner in self.REQUIRED_PUBLISHERS.items()
            if self.count_publishers(topic) < 1
        ]

    def on_presence(self, msg: Bool) -> None:
        present = bool(msg.data)
        if present == self.last_presence:
            return
        self.last_presence = present
        self.write("PRESENCE", "customer=ON" if present else "customer=OFF")

    def on_gesture(self, msg: String) -> None:
        gesture = str(msg.data).strip().upper()
        if gesture in {"NOD", "SHAKE"}:
            self.write("GESTURE", f"head={gesture}")

    def on_hand_quantity(self, msg: String) -> None:
        value = str(msg.data).strip()
        if value:
            self.write("GESTURE", f"hand={value}")

    def on_stt_status(self, msg: String) -> None:
        status = str(msg.data).strip()
        if not status or status == self.last_stt_status:
            return
        self.last_stt_status = status
        if status in {"no_speech", "too_quiet"}:
            self.write("⚠ PROBLEM", f"STT={status}")
        elif status.startswith("error"):
            self.write("❌ ERROR", f"STT={status}")
        elif status in {"listening", "speech_detected", "transcribing"}:
            self.write("STT", status)

    def on_voice_text(self, msg: String) -> None:
        text = str(msg.data).strip()
        if not text:
            return
        self.turn += 1
        self.write("STT TEXT", repr(text))

    def on_intent(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            self.write("⚠ PROBLEM", "NLU payload is not valid JSON")
            return

        intent = payload.get("intent") or "?"
        confidence = payload.get("intent_confidence")
        try:
            conf_text = f"{float(confidence):.3f}"
        except (TypeError, ValueError):
            conf_text = "?"

        status = payload.get("order_status") or "-"
        explicit = self.compact_explicit(payload.get("explicit_slots"))
        items = self.compact_items(payload.get("items"))
        reprompt = bool(payload.get("needs_reprompt"))

        self.write(
            "NLU",
            f"intent={intent} conf={conf_text} status={status} "
            f"explicit=[{explicit}] items=[{items}]",
        )

        try:
            low_conf = float(confidence) < 0.75
        except (TypeError, ValueError):
            low_conf = False
        if reprompt or low_conf:
            reasons = []
            if low_conf:
                reasons.append(f"low_conf={conf_text}")
            if reprompt:
                reasons.append("needs_reprompt=true")
            self.write("⚠ PROBLEM", "NLU " + ", ".join(reasons))

        fuzzy = payload.get("fuzzy_menu_recovery")
        if isinstance(fuzzy, dict):
            self.write(
                "NLU RECOV",
                f"fuzzy_menu={fuzzy.get('menu')} matched={fuzzy.get('matched_text')} "
                f"score={fuzzy.get('score')}",
            )

        multi = payload.get("multi_item_span_recovery")
        if isinstance(multi, dict):
            self.write(
                "NLU RECOV",
                f"multi_item count={multi.get('item_count')} "
                f"partial={multi.get('partial_item_indexes')}",
            )

    def on_decision(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            self.write("⚠ PROBLEM", "Decision payload is not valid JSON")
            return

        decision = payload.get("decision") or "?"
        state = payload.get("state") or "?"
        reason = payload.get("reason") or "-"
        missing = payload.get("missing_slot") or "-"
        waiting = payload.get("waiting_for")

        waiting_text = "-"
        if isinstance(waiting, dict):
            waiting_text = (
                f"item={waiting.get('item_id', '?')},slot={waiting.get('slot', '?')}"
            )

        self.write(
            "FSM",
            f"state={state} decision={decision} reason={reason} "
            f"missing={missing} waiting=[{waiting_text}]",
        )

        if decision in {"REPROMPT", "REORDER_REQUEST", "OUT_OF_POLICY"}:
            self.write("⚠ PROBLEM", f"dialogue decision={decision} reason={reason}")

    def on_response(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return
        speech = str(payload.get("speech") or "").strip()
        if speech:
            self.write("ROBOT SAY", repr(speech))

    def on_action(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return
        fields = []
        for key in ("face", "head", "arm"):
            value = payload.get(key)
            if value not in (None, "", "-"):
                fields.append(f"{key}={value}")
        if fields:
            self.write("ACTION", " ".join(fields))

    def on_tts_status(self, msg: String) -> None:
        status = str(msg.data).strip()
        if not status or status == self.last_tts_status:
            return
        self.last_tts_status = status
        if status.startswith("error"):
            self.write("❌ ERROR", f"TTS={status}")


def spin_node(node: Node) -> None:
    try:
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass


def print_banner(log_path: str) -> None:
    print(
        "\n"
        "============================================================\n"
        " Pumpkin DEMO DEBUG CONSOLE\n"
        "============================================================\n"
        "STT 문장 -> NLU -> FSM/Decision -> 로봇 응답/동작만 표시\n"
        "문제 신호: ⚠ PROBLEM / ❌ ERROR\n"
        f"이 화면 로그: {log_path}\n"
        "============================================================",
        flush=True,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", default="/tmp/pumpkin-logs/demo_debug_latest.log")
    args = parser.parse_args()

    print_banner(args.log_path)
    rclpy.init(args=None)
    node = DemoDebugConsole()
    thread = threading.Thread(target=spin_node, args=(node,), daemon=True)
    thread.start()

    try:
        deadline = time.monotonic() + 90.0
        while rclpy.ok() and time.monotonic() < deadline:
            missing = node.missing()
            if not missing:
                node.write("READY", "all core publishers connected")
                while rclpy.ok():
                    time.sleep(0.25)
                return 0
            time.sleep(0.25)

        node.write("❌ ERROR", "core ROS publishers did not become ready")
        for item in node.missing():
            node.write("MISSING", item)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if rclpy.ok():
            rclpy.shutdown()
        thread.join(timeout=1.0)
        try:
            node.destroy_node()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
