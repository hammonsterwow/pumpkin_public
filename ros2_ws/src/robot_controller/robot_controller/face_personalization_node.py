from __future__ import annotations

import json
import os
import threading
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from robot_controller.face_identity import parse_face_recognition_payload
from robot_controller.preorder import PreorderApiClient


class FacePersonalizationNode(Node):
    """Normalize face-recognition results for the order decision pipeline.

    Input topic:
      /face_recognition_result (std_msgs/String)

    Output topic:
      /customer_context (std_msgs/String)

    The output contract is stable even when the recognition payload is invalid
    or unmatched, so downstream nodes can safely treat it as anonymous context.
    """

    def __init__(self) -> None:
        super().__init__("face_personalization_node")

        self.subscription = self.create_subscription(
            String,
            "/face_recognition_result",
            self.face_result_callback,
            10,
        )
        self.decision_subscription = self.create_subscription(
            String,
            "/decision_result",
            self.decision_result_callback,
            10,
        )
        self.tts_status_subscription = self.create_subscription(
            String,
            "/tts/status",
            self.tts_status_callback,
            10,
        )
        self.publisher = self.create_publisher(String, "/customer_context", 10)
        self.preorder_client = PreorderApiClient()
        self.auto_pickup_delay_sec = max(
            0.0,
            float(os.getenv("PUMPKIN_PREORDER_AUTO_PICKUP_DELAY_SEC", "3.0")),
        )
        self._pickup_lock = threading.Lock()
        self._pending_pickup_order_id: str | None = None

        self.get_logger().info("Face Personalization Node started")
        self.get_logger().info(
            "Waiting for /face_recognition_result and publishing /customer_context"
        )

    def face_result_callback(self, msg: String) -> None:
        identity = parse_face_recognition_payload(msg.data)
        output = identity.to_dict()
        if identity.recognized and self.preorder_client.enabled:
            threading.Thread(
                target=self.publish_with_preorder, args=(output,), daemon=True
            ).start()
            return
        self.publish_context(output)

    def publish_with_preorder(self, output: dict) -> None:
        result = self.preorder_client.lookup(str(output.get("customer_id") or ""))
        if result.order is not None:
            output["preorder"] = result.order
        if result.error:
            self.get_logger().warning(
                f"Preorder lookup failed; continuing personalization: {result.error}"
            )
        self.publish_context(output)

    def decision_result_callback(self, msg: String) -> None:
        try:
            decision = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        if not isinstance(decision, dict):
            return
        if (
            decision.get("decision") != "GUIDE_CUSTOMER"
            or decision.get("response_key") != "preorder_pickup_ready"
        ):
            return

        response_args = decision.get("response_args")
        if not isinstance(response_args, dict):
            return
        order_id = str(response_args.get("order_id") or "").strip()
        if not order_id:
            return

        with self._pickup_lock:
            self._pending_pickup_order_id = order_id
        self.get_logger().info(
            f"READY preorder guidance armed for auto PICKED_UP: order_id={order_id}"
        )

    def tts_status_callback(self, msg: String) -> None:
        if msg.data.strip() != "done":
            return

        with self._pickup_lock:
            order_id = self._pending_pickup_order_id
            self._pending_pickup_order_id = None
        if not order_id:
            return

        threading.Thread(
            target=self.complete_pickup_after_delay,
            args=(order_id,),
            daemon=True,
        ).start()

    def complete_pickup_after_delay(self, order_id: str) -> None:
        time.sleep(self.auto_pickup_delay_sec)
        result = self.preorder_client.mark_picked_up(order_id)
        if result.order is not None:
            self.get_logger().info(
                "READY preorder automatically marked PICKED_UP after pickup guidance: "
                f"order_id={order_id}, delay={self.auto_pickup_delay_sec:.1f}s"
            )
            return
        self.get_logger().warning(
            "Failed to auto-complete preorder after pickup guidance; leaving current "
            f"server status unchanged: order_id={order_id}, error={result.error}"
        )

    def publish_context(self, output: dict) -> None:
        ros_msg = String()
        ros_msg.data = json.dumps(output, ensure_ascii=False)
        if not rclpy.ok():
            return
        try:
            self.publisher.publish(ros_msg)
        except Exception:
            if not rclpy.ok():
                return
            raise

        if output.get("recognized"):
            self.get_logger().info(
                "Recognized customer: "
                f"{output.get('name') or output.get('customer_id')} "
                f"(similarity={output.get('similarity')}, "
                f"preorder={bool(output.get('preorder'))})"
            )
        else:
            self.get_logger().info(
                f"Published anonymous customer context: reason={output.get('reason')}"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FacePersonalizationNode()
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
