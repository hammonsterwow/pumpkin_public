from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


SUPPORTED_HEAD_COMMANDS = {
    "CENTER",
    "NOD",
    "DOUBLE_NOD",
    "SHAKE",
    "TURN_LEFT",
    "TURN_RIGHT",
}

HEAD_COMMAND_ALIASES = {
    "LOOK_FORWARD": "CENTER",
    "LOOK_USER": "CENTER",
    "LOOK_SCREEN": "CENTER",
}


def normalize_head_command(value: object) -> str | None:
    command = str(value or "").strip().upper()
    command = HEAD_COMMAND_ALIASES.get(command, command)
    return command if command in SUPPORTED_HEAD_COMMANDS else None


class HeadMotionNode(Node):
    """Translate semantic robot head actions into motor-controller commands.

    This node consumes robot output only. Customer NOD/SHAKE perception is
    published on /user/head_gesture and never enters this executor directly.
    """

    def __init__(self) -> None:
        super().__init__("head_motion_node")
        self._guide_head_active = False

        self.robot_action_subscription = self.create_subscription(
            String,
            "/robot_action",
            self.robot_action_callback,
            10,
        )
        self.tts_status_subscription = self.create_subscription(
            String,
            "/tts/status",
            self.tts_status_callback,
            10,
        )
        self.motor_command_publisher = self.create_publisher(
            String,
            "/motor_command",
            10,
        )
        self.get_logger().info(
            "Head Motion Node started: /robot_action.head -> /motor_command"
        )

    def robot_action_callback(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f"Invalid /robot_action JSON: {exc}")
            return

        if not isinstance(payload, dict):
            self.get_logger().warning("Ignoring non-object /robot_action payload")
            return

        command = normalize_head_command(payload.get("head"))
        if command is None:
            self.get_logger().warning(
                f"Ignoring unsupported head action: {payload.get('head')!r}"
            )
            return

        if (
            self._guide_head_active
            and command not in {"CENTER", "TURN_LEFT", "TURN_RIGHT"}
        ):
            self.get_logger().info(
                f"Ignoring head command {command} while guide direction is held"
            )
            return

        if command in {"TURN_LEFT", "TURN_RIGHT"}:
            self._guide_head_active = True
        elif command == "CENTER":
            self._guide_head_active = False

        self.publish_motor_command(command)

    def tts_status_callback(self, msg: String) -> None:
        status = msg.data.strip().lower()
        if not self._guide_head_active:
            return
        if status == "done" or status.startswith("error"):
            self._guide_head_active = False
            self.publish_motor_command("CENTER")

    def publish_motor_command(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.motor_command_publisher.publish(msg)
        self.get_logger().info(f"Published motor command: {command}")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HeadMotionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
