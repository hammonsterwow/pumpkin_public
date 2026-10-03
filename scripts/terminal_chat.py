#!/usr/bin/env python3
"""Interactive terminal client for the Pumpkin ROS dialogue pipeline.

This script does not start the ROS nodes itself. Start the voice pipeline first,
then run this program in another terminal. User text is published to
``/voice_text`` and the rendered response from ``/response_result`` is printed
like a chatbot conversation.

By default, the terminal opens the next customer only after the customer confirms
that ordering is finished and ``NEXT_CUSTOMER_READY`` is emitted. Disable this
behavior with ``--no-auto-next-customer`` when debugging one session.
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


ORDER_COMPLETION_DECISIONS = frozenset({"NEXT_CUSTOMER_READY"})


@dataclass(frozen=True)
class ChatResponse:
    speech: str
    decision: str
    response_key: str
    state: str
    payload: dict[str, Any]


class TerminalChatNode(Node):
    def __init__(self, *, debug: bool = False) -> None:
        super().__init__("terminal_chat_client")
        self.debug = debug
        self.responses: queue.Queue[ChatResponse] = queue.Queue()
        self.last_decision: dict[str, Any] | None = None
        self.last_response: dict[str, Any] | None = None
        self.last_action: dict[str, Any] | None = None
        self.last_tts_status: str | None = None
        self._tts_done = threading.Event()

        self.voice_publisher = self.create_publisher(String, "/voice_text", 10)
        self.create_subscription(String, "/decision_result", self._on_decision, 10)
        self.create_subscription(String, "/response_result", self._on_response, 10)
        self.create_subscription(String, "/robot_action", self._on_action, 10)
        self.create_subscription(String, "/tts/status", self._on_tts_status, 10)

    @staticmethod
    def _decode(message: String) -> dict[str, Any] | None:
        raw = str(message.data).strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return payload if isinstance(payload, dict) else {"raw": payload}

    def _on_decision(self, message: String) -> None:
        payload = self._decode(message)
        if payload is None:
            return
        self.last_decision = payload
        if self.debug:
            print("\n[decision]", json.dumps(payload, ensure_ascii=False, indent=2))

    def _on_response(self, message: String) -> None:
        payload = self._decode(message)
        if payload is None:
            return
        self.last_response = payload
        response = ChatResponse(
            speech=str(payload.get("speech") or "").strip(),
            decision=str(payload.get("decision") or "UNKNOWN"),
            response_key=str(payload.get("response_key") or "unknown"),
            state=str(payload.get("state") or "UNKNOWN"),
            payload=payload,
        )
        self.responses.put(response)
        if self.debug:
            print("\n[response]", json.dumps(payload, ensure_ascii=False, indent=2))

    def _on_action(self, message: String) -> None:
        payload = self._decode(message)
        if payload is None:
            return
        self.last_action = payload
        if self.debug:
            print("\n[action]", json.dumps(payload, ensure_ascii=False, indent=2))

    def _on_tts_status(self, message: String) -> None:
        status = str(message.data).strip().lower()
        if not status:
            return
        self.last_tts_status = status
        if status == "done":
            self._tts_done.set()
        if self.debug:
            print(f"\n[tts/status] {status}")

    def wait_until_connected(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and rclpy.ok():
            if self.voice_publisher.get_subscription_count() > 0:
                return True
            time.sleep(0.1)
        return self.voice_publisher.get_subscription_count() > 0

    def clear_pending_responses(self) -> None:
        while True:
            try:
                self.responses.get_nowait()
            except queue.Empty:
                return

    def clear_terminal_state(self) -> None:
        self.clear_pending_responses()
        self.last_decision = None
        self.last_response = None
        self.last_action = None
        self.last_tts_status = None
        self._tts_done.clear()

    def prepare_for_user_turn(self) -> None:
        self.clear_pending_responses()
        self._tts_done.clear()

    def send_text(self, text: str) -> None:
        message = String()
        message.data = text
        self.voice_publisher.publish(message)

    def wait_for_response(self, timeout: float) -> ChatResponse | None:
        try:
            return self.responses.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_tts_done(self, timeout: float) -> bool:
        return self._tts_done.wait(timeout=max(0.0, timeout))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pumpkin ROS2 dialogue terminal client")
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="seconds to wait for each /response_result (default: 20)",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=10.0,
        help="seconds to wait for nlu_node subscription (default: 10)",
    )
    parser.add_argument(
        "--next-customer-timeout",
        type=float,
        default=20.0,
        help="seconds to wait for final order-completion TTS before opening the next customer (default: 20)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print decision, response, action and TTS status payloads",
    )
    parser.add_argument(
        "--no-auto-next-customer",
        dest="auto_next_customer",
        action="store_false",
        help="keep the current terminal session after an order is completed",
    )
    parser.set_defaults(auto_next_customer=True)
    return parser


def print_help() -> None:
    print(
        "명령어: /help, /state, /debug, /clear, /quit\n"
        "일반 문장을 입력하면 /voice_text로 전송합니다.\n"
        "고객이 주문 종료를 확인하고 완료 TTS가 끝나면 다음 손님으로 넘어갑니다."
    )


def print_state(node: TerminalChatNode) -> None:
    snapshot = {
        "decision": node.last_decision,
        "response": node.last_response,
        "action": node.last_action,
        "tts_status": node.last_tts_status,
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


def is_order_completion(response: ChatResponse) -> bool:
    return response.decision.upper() in ORDER_COMPLETION_DECISIONS


def open_next_customer(node: TerminalChatNode, customer_number: int) -> None:
    node.clear_terminal_state()
    print("\n" + "=" * 52)
    print(f"다음 손님 준비 완료 · 고객 {customer_number}")
    print("새 주문을 입력해 주세요.")
    print("=" * 52)


def run_chat(
    node: TerminalChatNode,
    *,
    timeout: float,
    auto_next_customer: bool,
    next_customer_timeout: float,
) -> None:
    print("\nPumpkin 터미널 대화 테스트")
    print_help()
    print("예: 아메리카노 하나요")
    customer_number = 1
    print(f"현재 고객: {customer_number}")

    while rclpy.ok():
        try:
            text = input("\n나 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n대화를 종료합니다.")
            return

        if not text:
            continue
        if text in {"/quit", "/exit", "quit", "exit"}:
            print("대화를 종료합니다.")
            return
        if text == "/help":
            print_help()
            continue
        if text == "/state":
            print_state(node)
            continue
        if text == "/debug":
            node.debug = not node.debug
            print(f"debug={'on' if node.debug else 'off'}")
            continue
        if text == "/clear":
            node.clear_terminal_state()
            print("터미널 대화 상태 표시를 초기화했습니다.")
            continue

        node.prepare_for_user_turn()
        node.send_text(text)
        response = node.wait_for_response(timeout)
        if response is None:
            print(
                "로봇 > 응답 시간이 초과되었습니다. "
                "nlu_node, decision_node, response_manager_node 로그를 확인하세요."
            )
            continue

        speech = response.speech or "(표시할 응답 문장이 없습니다.)"
        print(f"로봇 > {speech}")
        if node.debug:
            print(
                f"[meta] decision={response.decision}, "
                f"response_key={response.response_key}, state={response.state}"
            )

        if not auto_next_customer or not is_order_completion(response):
            continue

        print("[시스템] 주문 완료 음성이 끝나면 다음 손님으로 전환합니다.")
        if not node.wait_for_tts_done(next_customer_timeout):
            print(
                "[경고] /tts/status done을 받지 못해 자동 전환하지 않았습니다. "
                "TTS 노드 로그를 확인하거나 /clear 후 다시 시도하세요."
            )
            continue

        customer_number += 1
        open_next_customer(node, customer_number)


def main() -> int:
    args = build_parser().parse_args()
    rclpy.init(args=None)
    node = TerminalChatNode(debug=args.debug)
    spin_thread = threading.Thread(
        target=rclpy.spin,
        args=(node,),
        daemon=True,
        name="pumpkin-terminal-chat-spin",
    )
    spin_thread.start()

    try:
        if not node.wait_until_connected(args.connect_timeout):
            print(
                "오류: /voice_text 구독자를 찾지 못했습니다.\n"
                "먼저 scripts/run_ros_voice_nodes.sh를 실행하고 "
                "ROS 환경을 source 했는지 확인하세요."
            )
            return 1
        run_chat(
            node,
            timeout=args.timeout,
            auto_next_customer=args.auto_next_customer,
            next_customer_timeout=args.next_customer_timeout,
        )
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
