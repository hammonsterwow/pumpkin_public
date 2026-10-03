from __future__ import annotations

import json
import threading
import time
from typing import Any


EXPECTED_NODES = [
    "stt_node",
    "nlu_node",
    "decision_node",
    "response_manager_node",
    "action_node",
    "tts_node",
    "face_recognition_node",
]

DEFAULT_FACE_STATE: dict[str, Any] = {
    "detected": False,
    "matched": False,
    "customer_id": None,
    "similarity": None,
    "quality": None,
    "model": None,
    "latency_ms": None,
    "reason": "waiting_for_face_event",
    "updated_at": None,
}


class ROSWebBridge:
    """Observe the real ROS conversation pipeline for the manager web API.

    Text submitted by the test UI is published to ``/voice_text`` and follows
    NLU -> Decision -> Response Manager -> Action. The bridge never loads the
    NLU model or generates user-facing response text itself.
    """

    def __init__(self) -> None:
        self._setup_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._result_condition = threading.Condition(self._state_lock)
        self._node = None
        self._voice_publisher = None
        self._stt_trigger_publisher = None
        self._spin_thread = None
        self._request_id = 0
        self._stt_state = self._empty_state("idle")
        self._fsm_state = "UNKNOWN"
        self._face_state = dict(DEFAULT_FACE_STATE)

    def _empty_state(self, status: str) -> dict[str, Any]:
        return {
            "request_id": self._request_id,
            "status": status,
            "text": "",
            "analysis": None,
            "decision": None,
            "response": None,
            "response_text": "",
            "action": None,
            "error": None,
            "updated_at": time.time(),
        }

    def status(self) -> dict[str, Any]:
        try:
            self._ensure_node()
            active_nodes = sorted(
                name
                for name in set(self._node.get_node_names())
                if name in EXPECTED_NODES
            )
            stt_connected = self._stt_trigger_publisher.get_subscription_count() > 0
            nlu_connected = self._voice_publisher.get_subscription_count() > 0
            required_nodes = {
                "stt_node",
                "nlu_node",
                "decision_node",
                "response_manager_node",
                "action_node",
                "tts_node",
            }
            core_nodes_running = required_nodes.issubset(set(active_nodes))
            running = stt_connected and nlu_connected and core_nodes_running
        except Exception as error:
            return {
                "running": False,
                "state": "error",
                "nodes": [],
                "expected_nodes": EXPECTED_NODES,
                "stt_connected": False,
                "nlu_connected": False,
                "detail": str(error),
            }

        return {
            "running": running,
            "state": "running" if running else "degraded",
            "nodes": active_nodes,
            "expected_nodes": EXPECTED_NODES,
            "stt_connected": stt_connected,
            "nlu_connected": nlu_connected,
            "missing_nodes": sorted(set(EXPECTED_NODES) - set(active_nodes)),
        }

    def admin_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            pipeline_state = dict(self._stt_state)
            face_state = dict(self._face_state)
            fsm_state = self._fsm_state
        return {
            "system": self.status(),
            "fsm_state": fsm_state,
            "pipeline": pipeline_state,
            "face": face_state,
            "updated_at": time.time(),
        }

    def analyze_text(self, text: str, timeout: float = 15.0) -> dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("주문 문장을 입력해주세요.")

        self._ensure_node()
        if not self._wait_for_subscriber(self._voice_publisher):
            raise RuntimeError("nlu_node가 /voice_text 토픽에 연결되어 있지 않습니다.")

        from std_msgs.msg import String

        with self._result_condition:
            self._request_id += 1
            self._stt_state = self._empty_state("analyzing")
            self._stt_state["text"] = clean_text
            request_id = self._request_id

        message = String()
        message.data = clean_text
        self._voice_publisher.publish(message)

        deadline = time.monotonic() + timeout
        with self._result_condition:
            while time.monotonic() < deadline:
                if self._stt_state["request_id"] != request_id:
                    raise RuntimeError("새로운 음성 요청이 시작되어 기존 분석이 취소되었습니다.")
                if self._stt_state.get("error"):
                    raise RuntimeError(str(self._stt_state["error"]))
                if self._stt_state.get("analysis") and self._stt_state.get("action"):
                    return dict(self._stt_state)
                self._result_condition.wait(timeout=0.2)

        raise TimeoutError("ROS NLU, 판단, 응답 또는 로봇 행동 응답 시간이 초과되었습니다.")

    def trigger_stt(self) -> dict[str, Any]:
        self._ensure_node()
        if not self._wait_for_subscriber(self._stt_trigger_publisher):
            raise RuntimeError("stt_node가 /stt/trigger 토픽에 연결되어 있지 않습니다.")

        from std_msgs.msg import String

        with self._result_condition:
            self._request_id += 1
            self._stt_state = self._empty_state("requested")
            request_id = self._request_id

        message = String()
        message.data = "start"
        self._stt_trigger_publisher.publish(message)
        return {
            "published": True,
            "topic": "/stt/trigger",
            "command": "start",
            "request_id": request_id,
        }

    def stt_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._stt_state)

    def _ensure_node(self) -> None:
        if self._node is not None:
            return
        with self._setup_lock:
            if self._node is not None:
                return

            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import String

            if not rclpy.ok():
                rclpy.init(args=None)

            self._node = Node("web_api_bridge")
            self._voice_publisher = self._node.create_publisher(String, "/voice_text", 10)
            self._stt_trigger_publisher = self._node.create_publisher(
                String,
                "/stt/trigger",
                10,
            )
            self._node.create_subscription(String, "/stt/status", self._on_stt_status, 10)
            self._node.create_subscription(String, "/voice_text", self._on_voice_text, 10)
            self._node.create_subscription(
                String, "/intent_result", self._on_intent_result, 10
            )
            self._node.create_subscription(
                String, "/decision_result", self._on_decision_result, 10
            )
            self._node.create_subscription(
                String, "/response_result", self._on_response_result, 10
            )
            self._node.create_subscription(
                String, "/robot_action", self._on_robot_action, 10
            )
            self._node.create_subscription(String, "/fsm/state", self._on_fsm_state, 10)
            self._node.create_subscription(
                String, "/face/recognition", self._on_face_recognition, 10
            )

            self._spin_thread = threading.Thread(
                target=rclpy.spin,
                args=(self._node,),
                daemon=True,
                name="pumpkin-web-ros-spin",
            )
            self._spin_thread.start()

    @staticmethod
    def _wait_for_subscriber(publisher, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        return publisher.get_subscription_count() > 0

    def _on_stt_status(self, message) -> None:
        status = str(message.data).strip() or "unknown"
        with self._result_condition:
            self._stt_state["status"] = status
            self._stt_state["updated_at"] = time.time()
            if status.startswith("error:"):
                self._stt_state["error"] = status.split(":", 1)[1].strip()
            self._result_condition.notify_all()

    def _on_voice_text(self, message) -> None:
        text = str(message.data).strip()
        if not text:
            return
        with self._result_condition:
            self._stt_state["text"] = text
            self._stt_state["status"] = "analyzing"
            self._stt_state["updated_at"] = time.time()
            self._result_condition.notify_all()

    def _on_intent_result(self, message) -> None:
        payload = self._decode_json_message(message)
        if payload is None:
            return
        with self._result_condition:
            if not self._stt_state.get("text"):
                return
            self._stt_state["analysis"] = payload
            self._stt_state["status"] = "deciding"
            self._stt_state["updated_at"] = time.time()
            self._result_condition.notify_all()

    def _on_decision_result(self, message) -> None:
        payload = self._decode_json_message(message)
        if payload is None:
            return
        with self._result_condition:
            if not self._stt_state.get("text"):
                return
            self._stt_state["decision"] = payload
            self._stt_state["status"] = "responding"
            self._stt_state["updated_at"] = time.time()
            self._result_condition.notify_all()

    def _on_response_result(self, message) -> None:
        payload = self._decode_json_message(message)
        if payload is None:
            return
        with self._result_condition:
            if not self._stt_state.get("text"):
                return
            self._stt_state["response"] = payload
            self._stt_state["response_text"] = str(payload.get("speech") or "").strip()
            self._stt_state["status"] = "acting"
            self._stt_state["updated_at"] = time.time()
            self._result_condition.notify_all()

    def _on_robot_action(self, message) -> None:
        action = self._decode_json_message(message)
        if action is None:
            return
        with self._result_condition:
            if not self._stt_state.get("text"):
                return
            self._stt_state["action"] = action
            if not self._stt_state.get("response_text"):
                self._stt_state["response_text"] = str(action.get("tts") or "").strip()
            self._stt_state["status"] = "complete"
            self._stt_state["updated_at"] = time.time()
            self._result_condition.notify_all()

    @staticmethod
    def _decode_json_message(message) -> dict[str, Any] | None:
        raw = str(message.data).strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return payload if isinstance(payload, dict) else {"raw": payload}

    def _on_fsm_state(self, message) -> None:
        state = str(message.data).strip() or "UNKNOWN"
        with self._state_lock:
            self._fsm_state = state

    def _on_face_recognition(self, message) -> None:
        payload = self._decode_json_message(message)
        if payload is None:
            return
        next_state = dict(DEFAULT_FACE_STATE)
        next_state.update(payload)
        next_state["updated_at"] = time.time()
        with self._state_lock:
            self._face_state = next_state


ros_web_bridge = ROSWebBridge()
