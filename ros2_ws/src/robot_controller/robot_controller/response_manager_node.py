from __future__ import annotations

import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from .response_manager_order_exception import OrderExceptionAwareResponseManager


class ResponseManagerNode(Node):
    """Render Decision and execution-level response requests into user text."""

    def __init__(self):
        super().__init__("response_manager_node")
        self.declare_parameter("compact_response", False)
        self.compact_response = bool(
            self.get_parameter("compact_response").value
        )

        self.manager = OrderExceptionAwareResponseManager()
        self.decision_subscription = self.create_subscription(
            String,
            "/decision_result",
            self.decision_callback,
            10,
        )
        self.request_subscription = self.create_subscription(
            String,
            "/response_request",
            self.request_callback,
            10,
        )
        self.publisher = self.create_publisher(String, "/response_result", 10)
        self.get_logger().info(
            "Response Manager Node started "
            f"(compact_response={self.compact_response})"
        )

    def decision_callback(self, msg):
        self.render_and_publish(msg, source="decision")

    def request_callback(self, msg):
        self.render_and_publish(msg, source="execution")

    def render_and_publish(self, msg, source):
        try:
            payload = json.loads(msg.data)
            if not isinstance(payload, dict):
                raise ValueError("response input must be a JSON object")
            response = self.manager.render(
                payload,
                include_debug_context=not getattr(
                    self,
                    "compact_response",
                    False,
                ),
            )
            response["response_source"] = source
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            self.get_logger().error(f"Response rendering failed: {error}")
            response = {
                "decision": "RESPONSE_ERROR",
                "response_key": "response_error",
                "response_args": {},
                "speech": "처리 중 오류가 발생했습니다.",
                "display_text": "처리 오류",
                "reason": str(error),
                "response_source": source,
            }

        ros_msg = String()
        ros_msg.data = json.dumps(response, ensure_ascii=False)
        self.publisher.publish(ros_msg)
        self.get_logger().info(f"Published response: {ros_msg.data}")


def main(args=None):
    rclpy.init(args=args)
    node = ResponseManagerNode()
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
