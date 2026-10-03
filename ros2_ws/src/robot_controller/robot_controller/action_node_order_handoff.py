from __future__ import annotations

import json
import threading
import time

from std_msgs.msg import String

from .action_node import ActionNode
from .head_motion_node import HeadMotionNode


class OrderHandoffActionNode(ActionNode):
    """Action node variant for post-order handoff and persistent ROS VAD retries."""

    LISTEN_AFTER_TTS_DECISIONS = ActionNode.LISTEN_AFTER_TTS_DECISIONS | {
        "ORDER_CONFIRMED",
        "CONTINUE_ORDER",
        "GUIDE_CUSTOMER",
    }
    CONFIRMATION_LISTEN_DECISIONS = {
        "CONFIRM_ITEM",
        "CONFIRM_ORDER",
        "ORDER_CONFIRMED",
    }
    # These prompts commonly receive short one- or two-word answers. Reuse the
    # short-VAD trigger so replies such as "아이스", "네 잔이요", "라떼요" or
    # "레몬에이드" do not need to satisfy the conservative free-form-order VAD.
    SHORT_SLOT_LISTEN_DECISIONS = {
        "ASK_MENU",
        "ASK_TEMPERATURE",
        "ASK_QUANTITY",
        "MODIFY_ORDER",
    }
    RECOVERABLE_STT_FAILURES = {
        "empty",
        "no_speech",
        "too_quiet",
        "rejected",
    }
    STT_SUBSCRIBER_WAIT_TIMEOUT_SEC = 180.0
    STT_SUBSCRIBER_POLL_SEC = 0.25

    @classmethod
    def resolve_stt_trigger_mode(cls, source, previous_mode="start"):
        source_key = str(source or "").upper()
        if source_key == "STT_RETRY":
            return previous_mode if previous_mode in {"start", "confirm"} else "start"
        if source_key in cls.CONFIRMATION_LISTEN_DECISIONS:
            return "confirm"
        if source_key in cls.SHORT_SLOT_LISTEN_DECISIONS:
            return "confirm"
        return "start"

    def arm_listen_after_tts(self, source):
        previous_mode = getattr(self, "_stt_trigger_mode", "start")
        trigger_source = source
        if str(source or "").upper() == "GUIDE_CUSTOMER":
            trigger_source = getattr(self, "_guide_resume_source", None) or source
        self._guide_resume_source = None
        self._stt_trigger_mode = self.resolve_stt_trigger_mode(
            trigger_source,
            previous_mode=previous_mode,
        )
        super().arm_listen_after_tts(source)

    def response_callback(self, msg):
        """Cancel stale microphone capture when a visual answer wins the turn."""
        try:
            response_result = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError):
            response_result = {}

        resume_prompt = response_result.get("resume_prompt")
        if (
            response_result.get("decision") == "GUIDE_CUSTOMER"
            and isinstance(resume_prompt, dict)
        ):
            self._guide_resume_source = resume_prompt.get("decision")
        else:
            self._guide_resume_source = None

        if response_result.get("input_modality") == "VISION_GESTURE":
            cancel = String()
            cancel.data = "cancel"
            self.stt_trigger_publisher.publish(cancel)
            self.get_logger().info(
                "Published STT cancel because visual confirmation completed the turn"
            )

        super().response_callback(msg)

    def publish_head_command(self, head):
        """Delegate robot head execution to HeadMotionNode via /robot_action."""
        return None

    def trigger_pending_stt(self, reason):
        """Publish the listen trigger only after the STT node is subscribed."""
        with self._listen_lock:
            if not self._listen_pending:
                return

            if self.stt_trigger_publisher.get_subscription_count() <= 0:
                token = self._listen_token
                if getattr(self, "_stt_subscriber_wait_token", None) == token:
                    return
                self._stt_subscriber_wait_token = token
                self.get_logger().warning(
                    "STT subscriber is not ready yet. Keeping listen request "
                    f"pending: reason={reason}, token={token}"
                )
                threading.Thread(
                    target=self._wait_for_stt_subscriber,
                    args=(token, reason),
                    daemon=True,
                    name="pumpkin-stt-subscriber-wait",
                ).start()
                return

            trigger_mode = getattr(self, "_stt_trigger_mode", "start")
            if trigger_mode not in {"start", "confirm"}:
                trigger_mode = "start"
            self._listen_pending = False
            self._listen_seen_speaking = False
            self._stt_subscriber_wait_token = None

        msg = String()
        msg.data = trigger_mode
        self.stt_trigger_publisher.publish(msg)
        self.get_logger().info(
            f"Published STT trigger: {trigger_mode} ({reason})"
        )

    def _wait_for_stt_subscriber(self, token, reason):
        deadline = time.monotonic() + self.STT_SUBSCRIBER_WAIT_TIMEOUT_SEC
        while time.monotonic() < deadline:
            with self._listen_lock:
                if not self._listen_pending or self._listen_token != token:
                    return

            if self.stt_trigger_publisher.get_subscription_count() > 0:
                self.get_logger().info(
                    "STT subscriber became ready. Resuming pending listen: "
                    f"token={token}"
                )
                self.trigger_pending_stt(f"{reason}_subscriber_ready")
                return

            time.sleep(self.STT_SUBSCRIBER_POLL_SEC)

        with self._listen_lock:
            if getattr(self, "_stt_subscriber_wait_token", None) == token:
                self._stt_subscriber_wait_token = None
        self.get_logger().error(
            "Timed out waiting for STT subscriber; listen request remains "
            f"pending: token={token}"
        )

    def handle_stt_failed(self, status):
        """Retry recoverable recognition failures without discarding the order."""
        self.stt_retry_count += 1
        self.publish_response_request({
            "decision": "STT_RETRY",
            "response_key": "stt_retry",
            "response_args": {
                "status": status,
                "retry_count": self.stt_retry_count,
                "unlimited": True,
            },
            "reason": status,
            "state": "STT_RETRY",
        })
        self.get_logger().warning(
            "STT did not produce usable text. Asking again while preserving the active order. "
            f"retry_count={self.stt_retry_count}, status={status}"
        )

    def handle_stt_runtime_error(self, status):
        """Stop automatic listening when the microphone/runtime itself is broken.

        Recognition misses are safe to retry indefinitely, but an audio-device or
        STT runtime error cannot be fixed by asking the customer to repeat the same
        sentence. Publishing STT_FAILED once keeps the dialogue/order state intact
        while preventing TTS -> listen -> runtime-error -> TTS retry loops.
        """
        self.cancel_pending_listen()
        self.stt_retry_count = 0
        self.publish_response_request({
            "decision": "STT_FAILED",
            "response_key": "stt_failed",
            "response_args": {
                "status": status,
                "fatal": True,
            },
            "reason": status,
            "state": "STT_FAILED",
        })
        self.get_logger().warning(
            "STT runtime error detected. Stopping automatic retries while preserving "
            f"the active order: status={status}"
        )

    def stt_status_callback(self, msg):
        """Retry speech misses indefinitely, but stop on STT runtime errors."""
        status = msg.data.strip()
        if status in {
            "ready",
            "listening",
            "speech_detected",
            "recording",
            "transcribing",
            "done",
            "busy",
            "cancelled",
        }:
            return
        if status.startswith("error"):
            self.handle_stt_runtime_error(status)
            return
        if status in self.RECOVERABLE_STT_FAILURES:
            self.handle_stt_failed(status)

    def get_action_rule(self, response_result):
        decision = response_result.get("decision", "UNKNOWN")
        if decision == "NEXT_CUSTOMER_READY":
            return {
                "face": "NEUTRAL",
                "display": "IDLE",
                "head": "CENTER",
                # The hand wave belongs to the spoken final thanks, not the
                # initial customer greeting or intermediate order confirmation.
                "arm": "GOODBYE_WAVE",
                "priority": "NORMAL",
            }
        if decision == "CONTINUE_ORDER":
            return {
                "face": "QUESTION",
                "display": "ORDER_LISTEN",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "NORMAL",
            }
        if decision == "MODIFY_ORDER":
            return {
                "face": "QUESTION",
                "display": "MODIFY_ORDER",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "HIGH",
            }
        return super().get_action_rule(response_result)


def main(args=None):
    import rclpy
    from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor

    rclpy.init(args=args)
    action_node = OrderHandoffActionNode()
    head_motion_node = HeadMotionNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(action_node)
    executor.add_node(head_motion_node)

    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.remove_node(head_motion_node)
        executor.remove_node(action_node)
        head_motion_node.destroy_node()
        action_node.destroy_node()
        executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
