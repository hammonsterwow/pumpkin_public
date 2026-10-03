#!/usr/bin/env python3
"""Human-readable monitor for the real Pumpkin ROS interaction flow.

This monitor never simulates input. It only observes the running physical ROS
pipeline and exposes the few facts needed during an on-device order test:
customer presence, STT text, explicit NLU slots, FSM missing-slot decisions,
robot speech, face/head actions, and customer NOD/SHAKE.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool, String


class SimpleInteractionMonitor(Node):
    REQUIRED_PUBLISHERS = {
        "/human_presence": "vision",
        "/stt/status": "STT",
        "/voice_text": "STT text",
        "/intent_result": "NLU",
        "/decision_result": "Decision",
        "/response_result": "Response Manager",
        "/robot_action": "Action",
        "/tts/status": "TTS",
        "/motor_command": "Head Motion",
    }

    TEMP_KO = {"ICE": "아이스", "HOT": "핫"}
    FACE_KO = {
        "NEUTRAL": "기본",
        "SMILE": "웃는 표정",
        "HAPPY": "기쁜 표정",
        "THINKING": "생각하는 표정",
        "QUESTION": "질문 표정",
        "SAD": "아쉬운 표정",
        "ERROR": "오류 표정",
    }
    HEAD_KO = {
        "CENTER": "정면",
        "NOD": "끄덕이기",
        "SHAKE": "도리도리",
        "TURN_LEFT": "왼쪽 보기",
        "TURN_RIGHT": "오른쪽 보기",
        "LOOK_FORWARD": "정면",
        "LOOK_USER": "고객 보기",
        "LOOK_SCREEN": "화면 보기",
    }

    def __init__(self) -> None:
        super().__init__("robot_interaction_simple_terminal")
        self._lock = threading.Lock()
        self._last_presence: bool | None = None
        self._last_stt_status = ""
        self._last_tts_status = ""
        self._last_motor = ""

        self.create_subscription(Bool, "/human_presence", self.on_presence, 10)
        self.create_subscription(String, "/user/head_gesture", self.on_gesture, 10)
        self.create_subscription(String, "/stt/status", self.on_stt_status, 10)
        self.create_subscription(String, "/voice_text", self.on_voice_text, 10)
        self.create_subscription(String, "/intent_result", self.on_intent, 10)
        self.create_subscription(String, "/decision_result", self.on_decision, 10)
        self.create_subscription(String, "/response_result", self.on_response, 10)
        self.create_subscription(String, "/robot_action", self.on_action, 10)
        self.create_subscription(String, "/tts/status", self.on_tts_status, 10)
        self.create_subscription(String, "/face/status", self.on_face_status, 10)
        self.create_subscription(String, "/motor_command", self.on_motor, 10)

    def write(self, text: str) -> None:
        with self._lock:
            print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)

    @staticmethod
    def decode(message: String) -> dict[str, Any] | None:
        try:
            payload = json.loads(str(message.data))
        except (json.JSONDecodeError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None

    def missing(self) -> list[str]:
        return [
            f"{topic} ({owner})"
            for topic, owner in self.REQUIRED_PUBLISHERS.items()
            if self.count_publishers(topic) < 1
        ]

    def on_presence(self, msg: Bool) -> None:
        present = bool(msg.data)
        if present == self._last_presence:
            return
        self._last_presence = present
        if present:
            self.write("👤 고객을 감지했습니다.")
        else:
            self.write("👤 고객이 카메라에서 벗어났습니다.")

    def on_gesture(self, msg: String) -> None:
        gesture = str(msg.data).strip().upper()
        if gesture == "NOD":
            self.write("🙆 고객 끄덕임 인식 → '네'")
        elif gesture == "SHAKE":
            self.write("🙅 고객 도리도리 인식 → '아니요'")

    def on_stt_status(self, msg: String) -> None:
        status = str(msg.data).strip()
        if not status or status == self._last_stt_status:
            return
        self._last_stt_status = status
        labels = {
            "listening": "🎤 지금 말씀하세요.",
            "speech_detected": "🎙️ 목소리를 감지했습니다.",
            "recording": "🎙️ 듣고 있습니다...",
            "transcribing": "📝 음성을 글자로 바꾸는 중입니다...",
            "no_speech": "⚠️ 목소리를 듣지 못했습니다.",
            "too_quiet": "⚠️ 목소리가 너무 작습니다.",
        }
        if status.startswith("error"):
            self.write(f"❌ 음성 인식 오류: {status}")
        elif status in labels:
            self.write(labels[status])

    def on_voice_text(self, msg: String) -> None:
        text = str(msg.data).strip()
        if text:
            self.write(f"🗣️ 내가 한 말: {text}")

    def on_intent(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return

        explicit = payload.get("explicit_slots")
        if isinstance(explicit, dict):
            pieces: list[str] = []
            menu = explicit.get("menu")
            temp = explicit.get("temperature")
            quantity = explicit.get("quantity")
            if menu:
                pieces.append(f"메뉴={menu}")
            if temp:
                pieces.append(f"온도={self.TEMP_KO.get(str(temp).upper(), temp)}")
            if quantity is not None:
                pieces.append(f"수량={quantity}잔")
            if pieces:
                self.write("🧠 NLU가 직접 읽은 정보: " + ", ".join(pieces))
                return

        items = payload.get("items") or []
        if isinstance(items, list) and items:
            item = items[0] if isinstance(items[0], dict) else {}
            menu = item.get("menu") or "?"
            temp = item.get("temperature")
            quantity = item.get("quantity")
            temp_text = self.TEMP_KO.get(str(temp).upper(), temp) if temp else "?"
            quantity_text = f"{quantity}잔" if quantity is not None else "?"
            self.write(f"🧠 NLU 주문 해석: {menu} / {temp_text} / {quantity_text}")

    def on_decision(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return

        decision = str(payload.get("decision") or "")
        missing_slot = str(payload.get("missing_slot") or "")
        modality = str(payload.get("input_modality") or "")
        gesture = str(payload.get("user_gesture") or "")

        if modality == "VISION_GESTURE" and gesture in {"NOD", "SHAKE"}:
            self.write(
                "✅ 고객 제스처를 주문 확인에 반영했습니다: "
                + ("네" if gesture == "NOD" else "아니요")
            )

        slot_labels = {
            "menu": "메뉴",
            "temperature": "온도(아이스/핫)",
            "quantity": "수량",
        }
        if missing_slot in slot_labels:
            self.write(f"📋 Decision: 아직 {slot_labels[missing_slot]} 정보가 필요합니다.")
        elif decision == "CONFIRM_ORDER":
            self.write("✅ Decision: 주문 정보가 모두 채워졌습니다. 주문 확인 단계입니다.")
        elif decision == "ORDER_CONFIRMED":
            self.write("✅ Decision: 주문 확인을 받았습니다.")

    def on_response(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return
        speech = str(payload.get("speech") or "").strip()
        if speech:
            # Deliberately do NOT suppress duplicate text. A repeated prompt is
            # diagnostically meaningful during physical order testing.
            self.write(f"🤖 로봇: {speech}")

    def on_action(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return
        face = str(payload.get("face") or "-").upper()
        head = str(payload.get("head") or "-").upper()
        if face != "-" or head != "-":
            self.write(
                "🎭 출력 명령: "
                f"표정={self.FACE_KO.get(face, face)}, "
                f"고개={self.HEAD_KO.get(head, head)}"
            )

    def on_tts_status(self, msg: String) -> None:
        status = str(msg.data).strip()
        if not status or status == self._last_tts_status:
            return
        self._last_tts_status = status
        if status == "speaking":
            self.write("🔊 로봇 음성 재생 중")
        elif status.startswith("error"):
            self.write(f"❌ 스피커 오류: {status}")

    def on_face_status(self, msg: String) -> None:
        payload = self.decode(msg)
        if payload is None:
            return
        if str(payload.get("status") or "") != "ok":
            self.write(f"❌ 얼굴 LCD 오류: {payload.get('status')}")

    def on_motor(self, msg: String) -> None:
        command = str(msg.data).strip().upper()
        if not command:
            return
        if command == self._last_motor == "CENTER":
            return
        self._last_motor = command
        labels = {
            "CENTER": "정면을 봅니다.",
            "NOD": "끄덕입니다.",
            "SHAKE": "도리도리합니다.",
            "TURN_LEFT": "왼쪽을 봅니다.",
            "TURN_RIGHT": "오른쪽을 봅니다.",
        }
        if command in labels:
            self.write(f"🦾 로봇 고개: {labels[command]}")


def print_banner() -> None:
    print(
        "\n"
        "============================================================\n"
        " Pumpkin 실제 주문 테스트 - 쉬운 화면\n"
        "============================================================\n"
        "원본 ROS 로그는 터미널 1에 표시됩니다.\n"
        "여기에는 실제 주문 흐름과 NLU/Decision 핵심만 표시합니다.\n"
        "\n"
        "특히 수량 테스트에서는 다음 3줄을 확인하세요.\n"
        "  🗣️ 내가 한 말: 세 잔이요.\n"
        "  🧠 NLU가 직접 읽은 정보: 수량=3잔\n"
        "  ✅ Decision: 주문 정보가 모두 채워졌습니다...\n"
        "\nCtrl+C로 이 모니터만 종료합니다.\n"
        "============================================================",
        flush=True,
    )


def spin_node(node: Node) -> None:
    try:
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass


def main() -> int:
    rclpy.init(args=None)
    node = SimpleInteractionMonitor()
    thread = threading.Thread(target=spin_node, args=(node,), daemon=True)
    thread.start()

    try:
        print_banner()
        deadline = time.monotonic() + 240.0
        while rclpy.ok() and time.monotonic() < deadline:
            missing = node.missing()
            if not missing:
                node.write("✅ 로봇 준비 완료. 카메라 앞에 서세요.")
                while rclpy.ok():
                    time.sleep(0.25)
                return 0
            time.sleep(0.25)

        node.write("❌ 전체 ROS 연결이 준비되지 않았습니다.")
        for item in node.missing():
            node.write(f"   누락: {item}")
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
