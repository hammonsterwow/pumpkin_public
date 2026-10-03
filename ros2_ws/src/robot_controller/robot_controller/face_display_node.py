from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


SUPPORTED_FACE_NAMES = frozenset({
    "NEUTRAL",
    "SMILE",
    "HAPPY",
    "QUESTION",
    "ERROR",
})


def _ensure_project_root_on_path() -> Path | None:
    candidates: list[Path] = []

    configured_root = os.getenv("PUMPKIN_PROJECT_ROOT")
    if configured_root:
        candidates.append(Path(configured_root).expanduser())

    candidates.append(Path.cwd())
    candidates.extend(Path(__file__).resolve().parents)

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)

        if (resolved / "robot_face" / "jetson" / "face_controller.py").is_file():
            root_text = str(resolved)
            if root_text not in sys.path:
                sys.path.insert(0, root_text)
            return resolved

    return None


def normalize_face_name(value: Any) -> str:
    face = str(value or "").strip().upper()
    if face not in SUPPORTED_FACE_NAMES:
        allowed = ", ".join(sorted(SUPPORTED_FACE_NAMES))
        raise ValueError(f"Unsupported face {value!r}. Expected one of: {allowed}")
    return face


class FaceDisplayNode(Node):
    """Execute ``/robot_action.face`` on the ESP32-driven 3.5-inch LCD."""

    def __init__(self) -> None:
        super().__init__("face_display_node")

        self.declare_parameter("action_topic", "/robot_action")
        self.declare_parameter("status_topic", "/face/status")
        self.declare_parameter(
            "serial_port",
            os.getenv("PUMPKIN_ESP32_PORT", "auto"),
        )
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("reset_wait_sec", 2.0)
        self.declare_parameter("startup_face", "NEUTRAL")

        project_root = _ensure_project_root_on_path()
        if project_root is None:
            raise RuntimeError(
                "Could not find robot_face/jetson/face_controller.py. "
                "Set PUMPKIN_PROJECT_ROOT to the Pumpkin repository root."
            )

        try:
            from robot_face.jetson import FaceConnectionError, FaceController
        except ImportError as exc:
            raise RuntimeError(
                "ESP32 face controller dependencies are missing. Install them with: "
                "pip install -r robot_face/jetson/requirements.txt"
            ) from exc

        self._face_connection_error = FaceConnectionError
        self._controller = FaceController(
            port=str(self.get_parameter("serial_port").value),
            baudrate=int(self.get_parameter("baudrate").value),
            reset_wait=float(self.get_parameter("reset_wait_sec").value),
            auto_connect=False,
        )

        self.status_publisher = self.create_publisher(
            String,
            str(self.get_parameter("status_topic").value),
            10,
        )
        self.action_subscription = self.create_subscription(
            String,
            str(self.get_parameter("action_topic").value),
            self.action_callback,
            10,
        )

        self.get_logger().info(
            "Face display node started: "
            f"port={self.get_parameter('serial_port').value}, "
            f"baudrate={self.get_parameter('baudrate').value}, "
            f"project_root={project_root}"
        )

        startup_face = str(self.get_parameter("startup_face").value).strip()
        if startup_face:
            self.set_face_safely(startup_face, decision="STARTUP", force=True)

    def action_callback(self, msg: String) -> None:
        try:
            action = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().error(f"Invalid /robot_action JSON: {exc}")
            self.set_face_safely(
                "ERROR",
                decision="INVALID_ACTION_JSON",
                force=True,
            )
            return

        if not isinstance(action, dict):
            self.get_logger().error("/robot_action payload must be a JSON object.")
            self.set_face_safely(
                "ERROR",
                decision="INVALID_ACTION_PAYLOAD",
                force=True,
            )
            return

        raw_face = action.get("face")
        decision = str(action.get("decision") or "UNKNOWN")

        if raw_face is None or not str(raw_face).strip():
            self.get_logger().warning(
                f"Ignoring action without face command: decision={decision}"
            )
            return

        try:
            face = normalize_face_name(raw_face)
        except ValueError as exc:
            self.get_logger().error(f"{exc}; decision={decision}")
            self.set_face_safely(
                "ERROR",
                decision=f"INVALID_FACE:{decision}",
                force=True,
            )
            return

        self.set_face_safely(face, decision=decision)

    def set_face_safely(
        self,
        face: str,
        *,
        decision: str,
        force: bool = False,
    ) -> None:
        try:
            normalized = normalize_face_name(face)
            applied = self._controller.set_face(normalized, force=force)
        except (ValueError, self._face_connection_error, OSError) as exc:
            self.get_logger().error(
                f"Face LCD command failed: face={face}, decision={decision}, error={exc}"
            )
            self.publish_status(
                status="error",
                face=str(face).upper(),
                decision=decision,
                detail=str(exc),
            )
            return
        except Exception as exc:
            self.get_logger().error(
                f"Unexpected face LCD failure: face={face}, "
                f"decision={decision}, error={exc}"
            )
            self.publish_status(
                status="error",
                face=str(face).upper(),
                decision=decision,
                detail=str(exc),
            )
            return

        applied_name = str(getattr(applied, "value", applied))
        self.publish_status(
            status="ok",
            face=applied_name,
            decision=decision,
            port=str(self._controller.port or ""),
        )
        self.get_logger().info(
            f"Face LCD -> {applied_name} (decision={decision}, port={self._controller.port})"
        )

    def publish_status(
        self,
        *,
        status: str,
        face: str,
        decision: str,
        detail: str = "",
        port: str = "",
    ) -> None:
        payload = {
            "status": status,
            "face": face,
            "decision": decision,
        }
        if detail:
            payload["detail"] = detail
        if port:
            payload["port"] = port

        message = String()
        message.data = json.dumps(payload, ensure_ascii=False)
        self.status_publisher.publish(message)

    def destroy_node(self):
        try:
            self._controller.close()
        finally:
            return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FaceDisplayNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
