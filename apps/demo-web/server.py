#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
MENU_CATALOG_PATH = PROJECT_ROOT / "config" / "menu_catalog.json"
MAX_EVENTS = 300


FACE_LABELS = {
    "NEUTRAL": "기본 표정",
    "SMILE": "웃는 표정",
    "HAPPY": "기쁜 표정",
    "THINKING": "생각하는 표정",
    "SAD": "아쉬운 표정",
    "ERROR": "오류 표정",
}
HEAD_LABELS = {
    "CENTER": "정면 보기",
    "NOD": "끄덕이기",
    "DOUBLE_NOD": "두 번 끄덕이기",
    "SHAKE": "고개 흔들기",
    "TURN_LEFT": "왼쪽 보기",
    "TURN_RIGHT": "오른쪽 보기",
    "LOOK_FORWARD": "정면 보기",
    "LOOK_USER": "고객 보기",
    "LOOK_SCREEN": "화면 보기",
}
ARM_LABELS = {
    "WELCOME": "인사 동작",
    "IDLE": "대기",
    "NONE": "동작 없음",
    "-": "동작 없음",
}
DECISION_LABELS = {
    "START_ORDER": ("고객을 감지해 주문을 시작합니다.", "주문을 받을 준비를 합니다."),
    "ASK_MENU": ("메뉴 정보가 필요합니다.", "메뉴를 다시 질문합니다."),
    "ASK_QUANTITY": ("수량 정보가 필요합니다.", "몇 잔인지 다시 질문합니다."),
    "ASK_TEMPERATURE": ("HOT / ICE 정보가 필요합니다.", "온도를 다시 질문합니다."),
    "CONFIRM_ORDER": ("주문 정보가 모두 확인되었습니다.", "고객에게 주문 내용을 다시 확인합니다."),
    "ORDER_CONFIRMED": ("주문을 확정합니다.", "확정된 주문을 다음 단계로 전달합니다."),
    "MODIFY_ORDER": ("주문 내용을 수정합니다.", "고객의 수정 내용을 다시 반영합니다."),
    "REORDER_REQUEST": ("주문을 다시 받습니다.", "처음부터 주문 내용을 확인합니다."),
    "CANCEL_ORDER": ("주문을 취소합니다.", "현재 주문 흐름을 종료합니다."),
    "REPROMPT": ("입력 내용을 다시 확인해야 합니다.", "정확한 처리를 위해 한 번 더 질문합니다."),
    "GUIDE_CUSTOMER": ("매장 안내 요청으로 판단했습니다.", "안내 동작을 준비합니다."),
    "PAYMENT_GUIDE": ("결제 안내 요청으로 판단했습니다.", "결제 방법을 안내합니다."),
    "OUT_OF_POLICY": ("주문으로 처리하기 어려운 요청입니다.", "가능한 요청을 다시 안내합니다."),
}


def decode_json_message(message: Any) -> dict[str, Any] | None:
    raw = str(getattr(message, "data", "") or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return payload if isinstance(payload, dict) else {"raw": payload}


def load_menu_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    try:
        payload = json.loads(MENU_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return aliases

    for menu in payload.get("menus", []):
        if not isinstance(menu, dict):
            continue
        display = str(menu.get("name") or "").strip()
        if not display:
            continue
        candidates = [
            display,
            menu.get("eng_name"),
            menu.get("menu_id"),
            *(menu.get("aliases") or []),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            aliases[str(candidate).strip().lower()] = display
    return aliases


MENU_ALIASES = load_menu_aliases()


def display_menu(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "메뉴 미확인"
    return MENU_ALIASES.get(text.lower(), text)


def format_order_items(payload: dict[str, Any]) -> list[str]:
    items = payload.get("items")
    if not isinstance(items, list):
        order = payload.get("order")
        if isinstance(order, dict):
            items = order.get("items")
    if not isinstance(items, list):
        return []

    lines: list[str] = []
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        menu = display_menu(item.get("menu") or item.get("menu_name") or item.get("menu_id"))
        temperature = str(item.get("temperature") or "").strip().upper()
        quantity = item.get("quantity")
        parts = [menu]
        if temperature and temperature not in {"NONE", "NULL", "?"}:
            parts.append(temperature)
        if quantity not in {None, "", "?"}:
            parts.append(f"{quantity}잔")
        lines.append(" · ".join(parts))
    return lines


def describe_decision(payload: dict[str, Any]) -> tuple[str, str]:
    decision = str(payload.get("decision") or "UNKNOWN").upper()
    if decision == "REPROMPT":
        missing_slot = str(payload.get("missing_slot") or "").lower()
        if missing_slot == "menu":
            return "메뉴 정보가 아직 없습니다.", "메뉴를 다시 질문합니다."
        if missing_slot == "quantity":
            return "수량 정보가 아직 없습니다.", "몇 잔인지 다시 질문합니다."
        if missing_slot == "temperature":
            return "HOT / ICE 정보가 아직 없습니다.", "온도를 다시 질문합니다."
    return DECISION_LABELS.get(
        decision,
        ("다음 응답을 결정했습니다.", "현재 대화 상태에 맞는 동작을 실행합니다."),
    )


def format_action(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    face = str(payload.get("face") or "").strip().upper()
    head = str(payload.get("head") or "").strip().upper()
    arm = str(payload.get("arm") or "").strip().upper()
    if face and face not in {"NONE", "-"}:
        lines.append(f"표정 · {FACE_LABELS.get(face, face)}")
    if head and head not in {"NONE", "-"}:
        lines.append(f"고개 · {HEAD_LABELS.get(head, head)}")
    if arm and arm not in {"NONE", "-"}:
        lines.append(f"팔 · {ARM_LABELS.get(arm, arm)}")
    if not lines:
        lines.append("음성 응답을 실행합니다.")
    return lines


class DemoROSBridge:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._camera_condition = threading.Condition(self._lock)
        self._node = None
        self._spin_thread: threading.Thread | None = None
        self._running = False
        self._event_seq = 0
        self._state_version = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._latest_jpeg: bytes | None = None
        self._camera_seq = 0
        self._state: dict[str, Any] = {
            "presence": False,
            "gesture": None,
            "gesture_at": None,
            "stt_status": "",
            "tts_status": "",
            "user_text": "",
            "robot_text": "",
            "face": None,
            "connected": False,
        }

    def start(self) -> None:
        if self._running:
            return
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import CompressedImage
        from std_msgs.msg import Bool, String

        if not rclpy.ok():
            rclpy.init(args=None)

        self._node = Node("demo_web_bridge")
        self._node.create_subscription(Bool, "/human_presence", self._on_presence, 10)
        self._node.create_subscription(String, "/user/head_gesture", self._on_gesture, 10)
        self._node.create_subscription(String, "/stt/status", self._on_stt_status, 10)
        self._node.create_subscription(String, "/voice_text", self._on_voice_text, 10)
        self._node.create_subscription(String, "/intent_result", self._on_intent, 10)
        self._node.create_subscription(String, "/decision_result", self._on_decision, 10)
        self._node.create_subscription(String, "/response_result", self._on_response, 10)
        self._node.create_subscription(String, "/robot_action", self._on_robot_action, 10)
        self._node.create_subscription(String, "/tts/status", self._on_tts_status, 10)
        self._node.create_subscription(String, "/face/recognition", self._on_face_recognition, 10)
        # Optional integration point for the pre-order flow. It is harmless when
        # no publisher exists and gives the future order handoff one lightweight
        # JSON topic to drive the same demo screen.
        self._node.create_subscription(String, "/demo/preorder", self._on_preorder, 10)

        camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self._node.create_subscription(
            CompressedImage,
            "/demo/camera/compressed",
            self._on_camera,
            camera_qos,
        )

        self._running = True
        self._set_state(connected=True)
        self._spin_thread = threading.Thread(
            target=rclpy.spin,
            args=(self._node,),
            daemon=True,
            name="pumpkin-demo-web-ros-spin",
        )
        self._spin_thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        node = self._node
        self._node = None
        if node is not None:
            node.destroy_node()
        self._set_state(connected=False)
        with self._camera_condition:
            self._camera_condition.notify_all()

    def _set_state(self, **changes: Any) -> None:
        with self._lock:
            changed = False
            for key, value in changes.items():
                if self._state.get(key) != value:
                    self._state[key] = value
                    changed = True
            if changed:
                self._state_version += 1

    def _append_event(
        self,
        *,
        title: str,
        headline: str,
        detail: str = "",
        lines: list[str] | None = None,
        log_label: str,
        log_text: str,
        show_in_brain: bool = True,
    ) -> None:
        with self._lock:
            self._event_seq += 1
            event = {
                "seq": self._event_seq,
                "timestamp": time.time(),
                "title": title,
                "headline": headline,
                "detail": detail,
                "lines": list(lines or []),
                "log_label": log_label,
                "log_text": log_text,
                "show_in_brain": show_in_brain,
            }
            self._events.append(event)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": dict(self._state),
                "state_version": self._state_version,
                "event_seq": self._event_seq,
                "recent_logs": list(self._events)[-80:],
            }

    def updates_after(self, event_seq: int, state_version: int) -> dict[str, Any] | None:
        with self._lock:
            events = [event for event in self._events if event["seq"] > event_seq]
            state_changed = self._state_version != state_version
            if not events and not state_changed:
                return None
            return {
                "type": "update",
                "events": events,
                "event_seq": self._event_seq,
                "state_version": self._state_version,
                "state": dict(self._state) if state_changed else None,
            }

    def camera_stream(self) -> Iterator[bytes]:
        last_seq = -1
        while self._running:
            with self._camera_condition:
                self._camera_condition.wait_for(
                    lambda: self._camera_seq != last_seq or not self._running,
                    timeout=1.0,
                )
                if not self._running:
                    return
                if self._latest_jpeg is None or self._camera_seq == last_seq:
                    continue
                frame = self._latest_jpeg
                last_seq = self._camera_seq
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )

    def _on_camera(self, message: Any) -> None:
        frame = bytes(message.data)
        if not frame:
            return
        with self._camera_condition:
            self._latest_jpeg = frame
            self._camera_seq += 1
            self._camera_condition.notify_all()

    def _on_presence(self, message: Any) -> None:
        present = bool(message.data)
        previous = bool(self._state.get("presence"))
        self._set_state(presence=present)
        if present != previous:
            self._append_event(
                title="ROBOT VISION",
                headline="고객 감지" if present else "고객이 화면에서 벗어남",
                log_label="VISION",
                log_text="고객을 감지했습니다." if present else "고객이 카메라에서 벗어났습니다.",
                show_in_brain=False,
            )

    def _on_gesture(self, message: Any) -> None:
        gesture = str(message.data or "").strip().upper()
        if gesture not in {"NOD", "SHAKE"}:
            return
        now = time.time()
        self._set_state(gesture=gesture, gesture_at=now)
        meaning = "YES" if gesture == "NOD" else "NO"
        korean = "끄덕임" if gesture == "NOD" else "고개 흔들기"
        self._append_event(
            title="DECISION",
            headline=f"{korean}을 {meaning}로 인식했습니다.",
            detail="음성의 네 / 아니요와 같은 주문 확인 흐름에 반영합니다.",
            log_label="GESTURE",
            log_text=f"{gesture} → {meaning}",
        )

    def _on_stt_status(self, message: Any) -> None:
        status = str(message.data or "").strip()
        self._set_state(stt_status=status)
        if status in {"listening", "speech_detected", "transcribing"} or status.startswith("error"):
            labels = {
                "listening": "음성 입력 대기",
                "speech_detected": "사용자 발화 감지",
                "transcribing": "음성 인식 처리 중",
            }
            self._append_event(
                title="STT",
                headline=labels.get(status, status),
                log_label="STT",
                log_text=labels.get(status, status),
                show_in_brain=False,
            )

    def _on_voice_text(self, message: Any) -> None:
        text = str(message.data or "").strip()
        if not text:
            return
        self._set_state(user_text=text)
        self._append_event(
            title="STT",
            headline=text,
            log_label="USER",
            log_text=text,
            show_in_brain=False,
        )

    def _on_intent(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        lines = format_order_items(payload)
        if not lines:
            return
        self._append_event(
            title="ORDER UNDERSTANDING",
            headline=lines[0],
            lines=lines[1:],
            detail="주문 문장에서 메뉴 · 온도 · 수량을 추출했습니다.",
            log_label="NLU",
            log_text=" / ".join(lines),
        )

    def _on_decision(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        headline, detail = describe_decision(payload)
        decision = str(payload.get("decision") or "UNKNOWN")
        self._append_event(
            title="DECISION",
            headline=headline,
            detail=detail,
            log_label="DECISION",
            log_text=f"{decision} · {headline}",
        )

    def _on_response(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        speech = str(payload.get("speech") or "").strip()
        if not speech:
            return
        self._set_state(robot_text=speech)
        self._append_event(
            title="TTS",
            headline=speech,
            log_label="ROBOT",
            log_text=speech,
            show_in_brain=False,
        )

    def _on_robot_action(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        lines = format_action(payload)
        self._append_event(
            title="ROBOT ACTION",
            headline=lines[0],
            lines=lines[1:],
            detail="결정 결과를 로봇의 표정 · 고개 · 팔 동작으로 실행합니다.",
            log_label="ACTION",
            log_text=" / ".join(lines),
        )

    def _on_tts_status(self, message: Any) -> None:
        status = str(message.data or "").strip()
        self._set_state(tts_status=status)
        if status in {"speaking", "done"} or status.startswith("error"):
            label = {"speaking": "로봇 음성 출력 중", "done": "로봇 음성 출력 완료"}.get(status, status)
            self._append_event(
                title="TTS",
                headline=label,
                log_label="TTS",
                log_text=label,
                show_in_brain=False,
            )

    def _on_face_recognition(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        self._set_state(face=payload)
        if not bool(payload.get("matched")):
            return
        customer = str(
            payload.get("customer_name")
            or payload.get("name")
            or payload.get("customer_id")
            or "등록 고객"
        ).strip()
        self._append_event(
            title="DECISION",
            headline=f"{customer} 고객으로 확인했습니다.",
            detail="등록된 고객 정보를 바탕으로 개인화 주문 흐름을 준비합니다.",
            log_label="FACE",
            log_text=f"등록 고객 인식 · {customer}",
        )

    def _on_preorder(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        lines = format_order_items(payload)
        status = str(payload.get("status") or payload.get("order_status") or "").strip()
        headline = lines[0] if lines else "사전 주문 정보를 확인했습니다."
        extra = lines[1:]
        if status:
            extra.append(f"상태 · {status}")
        self._append_event(
            title="ORDER UNDERSTANDING",
            headline=headline,
            lines=extra,
            detail="매장 방문 전 접수된 사전 주문 내역입니다.",
            log_label="PRE-ORDER",
            log_text=" / ".join([headline, *extra]),
        )


bridge = DemoROSBridge()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bridge.start()
    try:
        yield
    finally:
        bridge.stop()


app = FastAPI(title="Pumpkin Demo Web", lifespan=lifespan)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def javascript() -> FileResponse:
    return FileResponse(APP_DIR / "app.js", media_type="application/javascript")


@app.get("/camera.mjpg")
def camera() -> StreamingResponse:
    return StreamingResponse(
        bridge.camera_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health() -> dict[str, Any]:
    snapshot = bridge.snapshot()
    return {
        "status": "ok" if snapshot["state"].get("connected") else "error",
        "event_seq": snapshot["event_seq"],
        "camera_connected": bridge._latest_jpeg is not None,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    snapshot = bridge.snapshot()
    event_seq = int(snapshot["event_seq"])
    state_version = int(snapshot["state_version"])
    await websocket.send_json({"type": "snapshot", **snapshot})
    last_heartbeat = time.monotonic()

    try:
        while True:
            await asyncio.sleep(0.08)
            update = bridge.updates_after(event_seq, state_version)
            if update is not None:
                event_seq = int(update["event_seq"])
                state_version = int(update["state_version"])
                await websocket.send_json(update)
                last_heartbeat = time.monotonic()
                continue
            if time.monotonic() - last_heartbeat >= 5.0:
                await websocket.send_json({"type": "heartbeat", "timestamp": time.time()})
                last_heartbeat = time.monotonic()
    except WebSocketDisconnect:
        return


def main() -> None:
    import uvicorn

    host = os.getenv("PUMPKIN_DEMO_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("PUMPKIN_DEMO_WEB_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
