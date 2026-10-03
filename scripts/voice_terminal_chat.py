#!/usr/bin/env python3
"""Voice-only terminal client for the Pumpkin ROS dialogue pipeline.

This program does not record audio or run Whisper by itself. It starts the
existing ROS ``stt_node`` through ``/stt/trigger`` (or simulates customer
presence), then observes the current VAD-driven STT result on ``/voice_text``
and the rendered robot response on ``/response_result``.

After the first turn, the normal Action Node flow keeps the conversation going:
TTS speaking -> TTS done -> /stt/trigger start.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class VoiceTerminalNode(Node):
    """Observe and start a voice dialogue without implementing STT locally."""

    def __init__(
        self,
        *,
        debug: bool = False,
        auto_next_customer: bool = False,
        next_customer_delay: float = 3.0,
    ) -> None:
        super().__init__("voice_terminal_chat_client")
        self.debug = debug
        self.auto_next_customer = auto_next_customer
        self.next_customer_delay = next_customer_delay

        self._print_lock = threading.Lock()
        self._presence_lock = threading.Lock()
        self._next_customer_scheduled = False
        self._last_stt_status = ""

        self.stt_trigger_publisher = self.create_publisher(
            String,
            "/stt/trigger",
            10,
        )
        self.human_presence_publisher = self.create_publisher(
            Bool,
            "/human_presence",
            10,
        )

        self.create_subscription(String, "/stt/status", self._on_stt_status, 10)
        self.create_subscription(String, "/voice_text", self._on_voice_text, 10)
        self.create_subscription(
            String,
            "/response_result",
            self._on_response,
            10,
        )
        self.create_subscription(String, "/tts/status", self._on_tts_status, 10)
        self.create_subscription(
            String,
            "/decision_result",
            self._on_decision,
            10,
        )
        self.create_subscription(String, "/robot_action", self._on_action, 10)

    def write(self, text: str = "") -> None:
        with self._print_lock:
            print(text, flush=True)

    @staticmethod
    def decode_json(message: String) -> dict[str, Any] | None:
        raw = str(message.data).strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return payload if isinstance(payload, dict) else {"raw": payload}

    def wait_until_ready(self, *, start_mode: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and rclpy.ok():
            stt_connected = self.stt_trigger_publisher.get_subscription_count() > 0
            voice_connected = self.count_publishers("/voice_text") > 0
            response_connected = self.count_publishers("/response_result") > 0
            presence_connected = (
                start_mode != "presence"
                or self.human_presence_publisher.get_subscription_count() > 0
            )
            if (
                stt_connected
                and voice_connected
                and response_connected
                and presence_connected
            ):
                return True
            time.sleep(0.1)
        return False

    def start_dialogue(self, start_mode: str) -> None:
        if start_mode == "presence":
            self.write("[시작] 가상 고객 접근 신호를 보냅니다.")
            self.publish_presence_cycle()
            return
        if start_mode == "listen":
            self.write("[시작] ROS STT VAD 청취를 바로 시작합니다.")
            self.publish_stt_start()
            return
        self.write("[시작] 모니터 전용 모드입니다. 실제 카메라 감지를 기다립니다.")

    def publish_stt_start(self) -> None:
        message = String()
        message.data = "start"
        self.stt_trigger_publisher.publish(message)

    def publish_presence_cycle(self) -> None:
        """Publish False -> True so Decision Node sees a customer-arrival edge."""
        with self._presence_lock:
            absent = Bool()
            absent.data = False
            self.human_presence_publisher.publish(absent)
            time.sleep(0.25)

            present = Bool()
            present.data = True
            self.human_presence_publisher.publish(present)

    def schedule_next_customer(self) -> None:
        if not self.auto_next_customer:
            return
        with self._presence_lock:
            if self._next_customer_scheduled:
                return
            self._next_customer_scheduled = True

        def worker() -> None:
            try:
                self.write(
                    f"[다음 고객] {self.next_customer_delay:.1f}초 뒤 "
                    "새 고객 접근을 자동으로 시뮬레이션합니다."
                )
                time.sleep(self.next_customer_delay)
                if rclpy.ok():
                    self.publish_presence_cycle()
            finally:
                with self._presence_lock:
                    self._next_customer_scheduled = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="pumpkin-next-customer-simulator",
        ).start()

    def _on_stt_status(self, message: String) -> None:
        status = str(message.data).strip()
        if not status or status == self._last_stt_status:
            return
        self._last_stt_status = status

        labels = {
            "ready": "[STT] 준비 완료",
            "listening": "[STT] 듣는 중입니다. 지금 말씀하세요.",
            "speech_detected": (
                "[STT] 음성을 감지했습니다. 말이 끝나면 VAD가 자동으로 "
                "녹음을 종료합니다."
            ),
            "transcribing": "[STT] 음성을 텍스트로 변환하는 중입니다.",
            "done": "[STT] 인식 완료",
            "no_speech": "[STT] 발화를 감지하지 못했습니다.",
            "too_quiet": "[STT] 목소리가 너무 작습니다.",
            "empty": "[STT] 인식된 문장이 없습니다.",
            "rejected": "[STT] 신뢰하기 어려운 인식 결과를 제외했습니다.",
            "busy": "[STT] 이미 녹음 또는 인식 중입니다.",
        }
        if status.startswith("error"):
            self.write(f"[STT 오류] {status}")
        else:
            self.write(labels.get(status, f"[STT] {status}"))

    def _on_voice_text(self, message: String) -> None:
        text = str(message.data).strip()
        if text:
            self.write(f"\n나(STT) > {text}")

    def _on_response(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None:
            return

        speech = str(payload.get("speech") or "").strip()
        decision = str(payload.get("decision") or "UNKNOWN")
        if speech:
            self.write(f"로봇 > {speech}")
        else:
            self.write(f"로봇 > (응답 문장 없음: decision={decision})")

        if self.debug:
            self.write(
                "[response] "
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )

        if decision == "NEXT_CUSTOMER_READY":
            self.write(
                "[상태] 주문 세션이 종료되어 IDLE입니다. "
                "실제 카메라의 다음 고객 감지 신호를 기다립니다."
            )
            self.schedule_next_customer()

    def _on_tts_status(self, message: String) -> None:
        status = str(message.data).strip()
        if status == "speaking":
            self.write("[TTS] 로봇 음성 재생 중")
        elif status == "done":
            self.write("[TTS] 재생 완료")
        elif status.startswith("error"):
            self.write(f"[TTS 오류] {status}")
        elif self.debug and status:
            self.write(f"[TTS] {status}")

    def _on_decision(self, message: String) -> None:
        if not self.debug:
            return
        payload = self.decode_json(message)
        if payload is not None:
            self.write(
                "[decision] "
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )

    def _on_action(self, message: String) -> None:
        if not self.debug:
            return
        payload = self.decode_json(message)
        if payload is not None:
            self.write(
                "[action] "
                + json.dumps(payload, ensure_ascii=False, indent=2)
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pumpkin ROS VAD voice dialogue terminal client",
    )
    parser.add_argument(
        "--start-mode",
        choices=("presence", "listen", "none"),
        default="presence",
        help=(
            "presence: simulate customer arrival and hear greeting; "
            "listen: trigger STT immediately; none: observe real vision events"
        ),
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=30.0,
        help="seconds to wait for ROS STT/dialogue topics (default: 30)",
    )
    parser.add_argument(
        "--auto-next-customer",
        action="store_true",
        help="simulate another customer after NEXT_CUSTOMER_READY",
    )
    parser.add_argument(
        "--next-customer-delay",
        type=float,
        default=3.0,
        help="delay before automatic next-customer simulation (default: 3)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print Decision, Response and Action JSON payloads",
    )
    return parser


def print_banner(start_mode: str) -> None:
    print("\nPumpkin ROS VAD 음성 대화 테스트", flush=True)
    print(
        "- 이 프로그램은 마이크 녹음이나 Whisper를 직접 실행하지 않습니다.\n"
        "- ROS stt_node의 /stt/trigger와 현재 VAD를 그대로 사용합니다.\n"
        "- 발화를 시작하면 자동 감지하고, 침묵이 이어지면 자동 종료합니다.\n"
        "- 엔터 입력은 사용하지 않습니다. 종료는 Ctrl+C입니다.\n"
        f"- 시작 모드: {start_mode}",
        flush=True,
    )


def main() -> int:
    args = build_parser().parse_args()
    rclpy.init(args=None)
    node = VoiceTerminalNode(
        debug=args.debug,
        auto_next_customer=args.auto_next_customer,
        next_customer_delay=max(0.0, args.next_customer_delay),
    )
    spin_thread = threading.Thread(
        target=rclpy.spin,
        args=(node,),
        daemon=True,
        name="pumpkin-voice-terminal-spin",
    )
    spin_thread.start()

    try:
        print_banner(args.start_mode)
        if not node.wait_until_ready(
            start_mode=args.start_mode,
            timeout=max(0.1, args.connect_timeout),
        ):
            node.write(
                "오류: ROS 음성 파이프라인 연결을 확인하지 못했습니다.\n"
                "먼저 scripts/run_ros_voice_nodes.sh를 실행하고, "
                "현재 터미널에서 ROS 환경을 source 하세요."
            )
            return 1

        node.write("[연결] STT, /voice_text, /response_result 연결 확인 완료")
        node.start_dialogue(args.start_mode)

        while rclpy.ok():
            time.sleep(0.2)
        return 0
    except KeyboardInterrupt:
        node.write("\n음성 대화 테스트를 종료합니다.")
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
