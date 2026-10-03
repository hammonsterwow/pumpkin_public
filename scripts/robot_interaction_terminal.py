#!/usr/bin/env python3
"""Live monitor for the complete Pumpkin physical ROS interaction flow.

This program does not simulate a customer and does not implement STT/TTS/vision
locally. It observes the real ROS graph started by run_robot_interaction_demo.sh.
Use --simple for a non-technical, human-readable physical demo view.
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


class RobotInteractionMonitor(Node):
    REQUIRED_PUBLISHERS = {
        "/human_presence": "vision_node",
        "/user/head_gesture": "vision_node head gesture",
        "/stt/status": "stt_node",
        "/voice_text": "stt_node",
        "/intent_result": "nlu_node",
        "/decision_result": "decision_node",
        "/response_result": "response_manager_node",
        "/robot_action": "action_node",
        "/tts/status": "tts_node",
        "/face/status": "face_display_node",
        "/motor_command": "head_motion_node",
    }

    FACE_KO = {
        "NEUTRAL": "기본 표정",
        "SMILE": "웃는 표정",
        "HAPPY": "기쁜 표정",
        "THINKING": "생각하는 표정",
        "SAD": "아쉬운 표정",
        "ERROR": "오류 표정",
    }
    HEAD_KO = {
        "CENTER": "정면 보기",
        "NOD": "끄덕이기",
        "SHAKE": "도리도리",
        "TURN_LEFT": "왼쪽 보기",
        "TURN_RIGHT": "오른쪽 보기",
        "LOOK_FORWARD": "정면 보기",
        "LOOK_USER": "고객 보기",
        "LOOK_SCREEN": "화면 보기",
        "-": "동작 없음",
    }
    ARM_KO = {
        "WELCOME": "인사 동작",
        "IDLE": "대기",
        "NONE": "동작 없음",
        "-": "동작 없음",
    }

    def __init__(self, *, debug_json: bool = False, simple: bool = False) -> None:
        super().__init__("robot_interaction_terminal")
        self.debug_json = debug_json
        self.simple = simple
        self._print_lock = threading.Lock()
        self._last_stt_status = ""
        self._last_tts_status = ""
        self._last_presence: bool | None = None
        self._last_motor_command = ""
        self._last_response = ""
        self._last_action_summary = ""
        self._last_face_summary = ""

        self.create_subscription(Bool, "/human_presence", self.on_presence, 10)
        self.create_subscription(String, "/user/head_gesture", self.on_user_gesture, 10)
        self.create_subscription(String, "/stt/status", self.on_stt_status, 10)
        self.create_subscription(String, "/voice_text", self.on_voice_text, 10)
        self.create_subscription(String, "/intent_result", self.on_intent, 10)
        self.create_subscription(String, "/decision_result", self.on_decision, 10)
        self.create_subscription(String, "/response_result", self.on_response, 10)
        self.create_subscription(String, "/robot_action", self.on_robot_action, 10)
        self.create_subscription(String, "/tts/status", self.on_tts_status, 10)
        self.create_subscription(String, "/face/status", self.on_face_status, 10)
        self.create_subscription(String, "/motor_command", self.on_motor_command, 10)

    def stamp(self) -> str:
        return time.strftime("%H:%M:%S")

    def write(self, text: str = "") -> None:
        with self._print_lock:
            if text:
                print(f"[{self.stamp()}] {text}", flush=True)
            else:
                print(flush=True)

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

    def debug(self, label: str, payload: dict[str, Any] | None) -> None:
        if self.debug_json and not self.simple and payload is not None:
            self.write(f"{label} JSON = {json.dumps(payload, ensure_ascii=False)}")

    def missing_connections(self) -> list[str]:
        missing: list[str] = []
        for topic, owner in self.REQUIRED_PUBLISHERS.items():
            if self.count_publishers(topic) < 1:
                missing.append(f"{topic} ({owner})")
        if self.count_subscribers("/motor_command") < 1:
            missing.append("/motor_command subscriber (motor_controller_node)")
        return missing

    def wait_until_ready(self, timeout: float) -> tuple[bool, list[str]]:
        deadline = time.monotonic() + timeout
        missing: list[str] = []
        while rclpy.ok() and time.monotonic() < deadline:
            missing = self.missing_connections()
            if not missing:
                return True, []
            time.sleep(0.25)
        return False, missing or self.missing_connections()

    def on_presence(self, message: Bool) -> None:
        present = bool(message.data)
        if self._last_presence is present:
            return
        self._last_presence = present
        if self.simple:
            self.write("👤 고객을 감지했습니다." if present else "👤 고객이 카메라에서 벗어났습니다.")
            return
        if present:
            self.write("CAMERA  | 고객 감지됨 -> 주문 세션 시작 조건 충족")
        else:
            self.write("CAMERA  | 고객 없음")

    def on_user_gesture(self, message: String) -> None:
        gesture = str(message.data).strip().upper()
        if not gesture:
            return
        if self.simple:
            if gesture == "NOD":
                self.write("🙆 고객 끄덕임을 인식했습니다. → '네'")
            elif gesture == "SHAKE":
                self.write("🙅 고객 도리도리를 인식했습니다. → '아니요'")
            return
        meaning = {"NOD": "AFFIRM(네)", "SHAKE": "DENY(아니요)"}.get(gesture, "UNKNOWN")
        self.write(f"GESTURE | 손님 {gesture} 인식 -> {meaning}")

    def on_stt_status(self, message: String) -> None:
        status = str(message.data).strip()
        if not status or status == self._last_stt_status:
            return
        self._last_stt_status = status
        if self.simple:
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
            return

        labels = {
            "ready": "준비 완료",
            "listening": "VAD 청취 중 - 지금 말씀하세요",
            "speech_detected": "발화 시작 감지",
            "recording": "녹음 중",
            "transcribing": "Whisper 변환 중",
            "done": "음성 인식 완료",
            "no_speech": "발화 없음",
            "too_quiet": "음량 너무 작음",
            "empty": "텍스트 없음",
            "rejected": "인식 결과 제외",
            "busy": "이미 처리 중",
        }
        if status.startswith("error"):
            self.write(f"STT ERR | {status}")
        else:
            self.write(f"STT     | {labels.get(status, status)}")

    def on_voice_text(self, message: String) -> None:
        text = str(message.data).strip()
        if text:
            self.write(f"🗣️ 내가 한 말: {text}" if self.simple else f"USER    | {text}")

    @staticmethod
    def summarize_items(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            return ""
        chunks: list[str] = []
        for item in items[:4]:
            if not isinstance(item, dict):
                continue
            menu = item.get("menu") or "?"
            temperature = item.get("temperature") or "?"
            quantity = item.get("quantity")
            chunks.append(f"{menu}/{temperature}/{quantity if quantity is not None else '?'}")
        return ", ".join(chunks)

    def on_intent(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None or self.simple:
            return
        intent = str(payload.get("intent") or "UNKNOWN")
        confidence = payload.get("confidence")
        confidence_text = "?"
        try:
            confidence_text = f"{float(confidence):.3f}"
        except (TypeError, ValueError):
            pass
        items = self.summarize_items(payload)
        suffix = f" | {items}" if items else ""
        self.write(f"NLU     | intent={intent} confidence={confidence_text}{suffix}")
        self.debug("NLU", payload)

    def on_decision(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None:
            return
        decision = str(payload.get("decision") or "UNKNOWN")
        state = str(payload.get("state") or "?")
        modality = str(payload.get("input_modality") or "VOICE/NLU")
        gesture = str(payload.get("user_gesture") or "")
        if self.simple:
            if modality == "VISION_GESTURE" and gesture in {"NOD", "SHAKE"}:
                meaning = "네" if gesture == "NOD" else "아니요"
                self.write(f"✅ 제스처를 '{meaning}'로 주문 흐름에 반영했습니다.")
            return
        gesture_text = f" gesture={gesture}" if gesture else ""
        self.write(f"DECIDE  | {decision} state={state} input={modality}{gesture_text}")
        if modality == "VISION_GESTURE" and gesture in {"NOD", "SHAKE"}:
            self.write(f"CHECK   | 손님 {gesture}가 음성 긍정/부정과 동일한 FSM 경로로 처리됨")
        self.debug("DECISION", payload)

    def on_response(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None:
            return
        speech = str(payload.get("speech") or "").strip()
        decision = str(payload.get("decision") or "UNKNOWN")
        if self.simple:
            if speech and speech != self._last_response:
                self._last_response = speech
                self.write(f"🤖 로봇: {speech}")
            return
        if speech:
            self.write(f"ROBOT   | {speech}  ({decision})")
        else:
            self.write(f"ROBOT   | speech 없음 ({decision})")
        self.debug("RESPONSE", payload)

    def on_robot_action(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None:
            return
        face = str(payload.get("face") or "-").upper()
        head = str(payload.get("head") or "-").upper()
        arm = str(payload.get("arm") or "-").upper()
        decision = str(payload.get("decision") or "UNKNOWN")
        if self.simple:
            summary = (
                f"표정={self.FACE_KO.get(face, face)}, "
                f"고개={self.HEAD_KO.get(head, head)}, "
                f"팔={self.ARM_KO.get(arm, arm)}"
            )
            if summary != self._last_action_summary:
                self._last_action_summary = summary
                self.write(f"🎭 로봇 동작: {summary}")
            return
        self.write(f"ACTION  | decision={decision} face={face} head={head} arm={arm}")
        self.debug("ACTION", payload)

    def on_tts_status(self, message: String) -> None:
        status = str(message.data).strip()
        if not status or status == self._last_tts_status:
            return
        self._last_tts_status = status
        if self.simple:
            if status == "speaking":
                self.write("🔊 로봇이 말하고 있습니다.")
            elif status.startswith("error"):
                self.write(f"❌ 스피커 출력 오류: {status}")
            return
        if status == "speaking":
            self.write("SPEAKER | TTS 재생 중")
        elif status == "done":
            self.write("SPEAKER | TTS 재생 완료 -> 필요한 경우 다음 VAD 청취로 전환")
        elif status.startswith("error"):
            self.write(f"SPK ERR | {status}")
        else:
            self.write(f"SPEAKER | {status}")

    def on_face_status(self, message: String) -> None:
        payload = self.decode_json(message)
        if payload is None:
            return
        status = str(payload.get("status") or "?")
        face = str(payload.get("face") or "?").upper()
        decision = str(payload.get("decision") or "?")
        if self.simple:
            if status == "ok":
                summary = self.FACE_KO.get(face, face)
                if summary != self._last_face_summary:
                    self._last_face_summary = summary
                    self.write(f"🖥️ 얼굴 LCD: {summary}")
            else:
                self.write(f"❌ 얼굴 LCD 오류: {status}")
            return
        if status == "ok":
            self.write(f"LCD     | face={face} 적용 완료 ({decision})")
        else:
            detail = str(payload.get("detail") or "")
            self.write(f"LCD ERR | face={face} status={status} {detail}")
        self.debug("FACE", payload)

    def on_motor_command(self, message: String) -> None:
        command = str(message.data).strip().upper()
        if not command:
            return
        if command == self._last_motor_command == "CENTER":
            return
        self._last_motor_command = command
        if self.simple:
            physical = {
                "NOD": "끄덕였습니다.",
                "SHAKE": "도리도리했습니다.",
                "TURN_LEFT": "왼쪽을 봅니다.",
                "TURN_RIGHT": "오른쪽을 봅니다.",
                "CENTER": "정면을 봅니다.",
            }.get(command)
            if physical:
                self.write(f"🦾 로봇 고개: {physical}")
            return
        physical = {
            "NOD": "로봇 실제 끄덕임",
            "SHAKE": "로봇 실제 도리도리",
            "TURN_LEFT": "로봇 왼쪽 회전",
            "TURN_RIGHT": "로봇 오른쪽 회전",
            "CENTER": "로봇 정면 복귀",
        }.get(command, "모터 명령")
        self.write(f"MOTOR   | {command} -> {physical}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor the full Pumpkin ROS physical interaction flow")
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=60.0,
        help="seconds to wait for every required ROS component (default: 60)",
    )
    parser.add_argument(
        "--debug-json",
        action="store_true",
        help="also print raw JSON payloads for NLU/Decision/Response/Action",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="show only human-readable customer/robot events",
    )
    return parser


def print_banner(simple: bool) -> None:
    if simple:
        print(
            "\n"
            "============================================================\n"
            " Pumpkin 로봇 주문 테스트 - 쉬운 화면\n"
            "============================================================\n"
            "이 화면에는 테스트할 때 필요한 내용만 표시됩니다.\n"
            "원본 ROS 로그는 다른 터미널에서 확인하세요.\n"
            "\n"
            "  👤 카메라 고객 감지\n"
            "  🎤 말할 타이밍 / 🗣️ 인식된 내 말\n"
            "  🙆🙅 고객 끄덕임/도리도리\n"
            "  🤖 로봇이 하는 말\n"
            "  🖥️ 얼굴 표정 / 🦾 고개 동작\n"
            "\n"
            "Ctrl+C로 이 모니터만 종료합니다.\n"
            "============================================================",
            flush=True,
        )
        return

    print(
        "\n"
        "============================================================\n"
        " Pumpkin 실제 로봇 주문 통합 모니터\n"
        "============================================================\n"
        "이 프로그램은 가상 입력을 만들지 않습니다.\n"
        "카메라/마이크/ROS/스피커/LCD/PCA9685의 실제 이벤트를 관찰합니다.\n"
        "Ctrl+C로 종료합니다.\n"
        "============================================================",
        flush=True,
    )


def main() -> int:
    args = build_parser().parse_args()
    rclpy.init(args=None)
    node = RobotInteractionMonitor(debug_json=args.debug_json, simple=args.simple)
    spin_thread = threading.Thread(
        target=rclpy.spin,
        args=(node,),
        daemon=True,
        name="pumpkin-robot-monitor-spin",
    )
    spin_thread.start()

    try:
        print_banner(args.simple)
        ready, missing = node.wait_until_ready(max(0.1, args.ready_timeout))
        if not ready:
            if args.simple:
                node.write("❌ 로봇 프로그램이 아직 전부 준비되지 않았습니다.")
                node.write("   먼저 터미널 1의 실행 로그를 확인하세요.")
            else:
                node.write("READY ERR | 전체 ROS 연결이 준비되지 않았습니다.")
                for item in missing:
                    node.write(f"MISSING | {item}")
                node.write("TIP     | 먼저 scripts/run_robot_interaction_demo.sh를 실행하세요.")
            return 1

        if args.simple:
            node.write("✅ 로봇 준비 완료. 카메라 앞에 서세요.")
        else:
            node.write("READY   | 전체 ROS perception -> action -> hardware 연결 확인")
            node.write("WAIT    | 실제 카메라의 고객 감지를 기다립니다.")
        while rclpy.ok():
            time.sleep(0.25)
        return 0
    except KeyboardInterrupt:
        if args.simple:
            node.write("모니터를 종료합니다.")
        else:
            node.write("STOP    | 통합 모니터를 종료합니다.")
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
