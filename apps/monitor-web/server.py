#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from monitor_state import MonitorState, decode_json_message

APP_DIR = Path(__file__).resolve().parent


class MonitorROSBridge:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._node = None
        self._spin_thread: threading.Thread | None = None
        self._running = False
        self._state = MonitorState()

    def start(self) -> None:
        if self._running:
            return

        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import Bool, String

        if not rclpy.ok():
            rclpy.init(args=None)

        self._node = Node("monitor_web_bridge")
        self._node.create_subscription(Bool, "/human_presence", self._on_presence, 10)
        self._node.create_subscription(String, "/stt/status", self._on_stt_status, 10)
        self._node.create_subscription(String, "/voice_text", self._on_voice_text, 10)
        self._node.create_subscription(String, "/intent_result", self._on_intent_result, 10)
        self._node.create_subscription(String, "/decision_result", self._on_decision_result, 10)
        self._node.create_subscription(String, "/response_result", self._on_response_result, 10)
        self._node.create_subscription(String, "/tts/status", self._on_tts_status, 10)

        self._running = True
        with self._lock:
            self._state.set_connected(True)
        self._spin_thread = threading.Thread(
            target=rclpy.spin,
            args=(self._node,),
            daemon=True,
            name="pumpkin-monitor-web-ros-spin",
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
        with self._lock:
            self._state.set_connected(False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._state.snapshot()

    def _on_presence(self, message: Any) -> None:
        with self._lock:
            self._state.update_presence(bool(message.data))

    def _on_stt_status(self, message: Any) -> None:
        with self._lock:
            self._state.update_stt_status(str(message.data or ""))

    def _on_voice_text(self, message: Any) -> None:
        with self._lock:
            self._state.update_user_text(str(message.data or ""))

    def _on_intent_result(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        with self._lock:
            self._state.update_nlu(payload)

    def _on_decision_result(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        with self._lock:
            self._state.update_decision(payload)

    def _on_response_result(self, message: Any) -> None:
        payload = decode_json_message(message)
        if payload is None:
            return
        speech = str(payload.get("speech") or "").strip()
        with self._lock:
            self._state.update_robot_text(speech)

    def _on_tts_status(self, message: Any) -> None:
        with self._lock:
            self._state.update_tts_status(str(message.data or ""))


bridge = MonitorROSBridge()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bridge.start()
    try:
        yield
    finally:
        bridge.stop()


app = FastAPI(title="Pumpkin 5-inch Customer Monitor", lifespan=lifespan)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def javascript() -> FileResponse:
    return FileResponse(APP_DIR / "app.js", media_type="application/javascript")


@app.get("/health")
def health() -> dict[str, Any]:
    snapshot = bridge.snapshot()
    return {
        "status": "ok" if snapshot.get("connected") else "error",
        "version": snapshot.get("version", 0),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    last_version = -1
    last_heartbeat = time.monotonic()

    try:
        while True:
            snapshot = bridge.snapshot()
            version = int(snapshot.get("version", 0))
            if version != last_version:
                await websocket.send_json({"type": "snapshot", "state": snapshot})
                last_version = version
                last_heartbeat = time.monotonic()
            elif time.monotonic() - last_heartbeat >= 5.0:
                await websocket.send_json({"type": "heartbeat", "timestamp": time.time()})
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.08)
    except WebSocketDisconnect:
        return


def main() -> None:
    import uvicorn

    host = os.getenv("PUMPKIN_MONITOR_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("PUMPKIN_MONITOR_WEB_PORT", "8770"))
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
