import json
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from rclpy.executors import ExternalShutdownException

from .head_motion_node import HeadMotionNode


class _CoreActionNode(Node):
    LISTEN_AFTER_TTS_DECISIONS = {
        "START_ORDER",
        "CONFIRM_ITEM",
        "CONFIRM_ORDER",
        "REPROMPT",
        "ASK_MENU",
        "ASK_TEMPERATURE",
        "ASK_QUANTITY",
        "OUT_OF_POLICY",
        "REORDER_REQUEST",
        "MODIFY_ORDER",
        "STT_RETRY",
    }

    def __init__(self):
        super().__init__("action_node")

        self.declare_parameter("stt_trigger_topic", "/stt/trigger")
        self.declare_parameter("stt_status_topic", "/stt/status")
        self.declare_parameter("tts_status_topic", "/tts/status")
        self.declare_parameter("tts_done_timeout_sec", 12.0)
        self.declare_parameter("max_stt_retries", 2)

        self.tts_done_timeout_sec = float(
            self.get_parameter("tts_done_timeout_sec").value
        )
        self.max_stt_retries = int(self.get_parameter("max_stt_retries").value)
        self.stt_retry_count = 0

        self._listen_lock = threading.Lock()
        self._listen_token = 0
        self._listen_pending = False
        self._listen_seen_speaking = False
        self._guide_head_active = False

        self.subscription = self.create_subscription(
            String,
            "/response_result",
            self.response_callback,
            10,
        )
        self.stt_status_subscription = self.create_subscription(
            String,
            str(self.get_parameter("stt_status_topic").value),
            self.stt_status_callback,
            10,
        )
        self.tts_status_subscription = self.create_subscription(
            String,
            str(self.get_parameter("tts_status_topic").value),
            self.tts_status_callback,
            10,
        )
        self.publisher = self.create_publisher(String, "/robot_action", 10)
        self.motor_command_publisher = self.create_publisher(String, "/motor_command", 10)
        self.response_request_publisher = self.create_publisher(
            String,
            "/response_request",
            10,
        )
        self.stt_trigger_publisher = self.create_publisher(
            String,
            str(self.get_parameter("stt_trigger_topic").value),
            10,
        )

        self.get_logger().info("Action Node started")

    def response_callback(self, msg):
        try:
            response_result = json.loads(msg.data)
            action = self.make_action(response_result)
        except json.JSONDecodeError:
            action = self.make_error_action("invalid_json", raw_message=msg.data)
        except Exception as exc:
            action = self.make_error_action(str(exc), raw_message=msg.data)

        decision = action.get("decision")
        should_listen = decision in self.LISTEN_AFTER_TTS_DECISIONS

        if should_listen:
            if decision != "STT_RETRY":
                self.stt_retry_count = 0
            self.arm_listen_after_tts(decision)
        else:
            self.cancel_pending_listen()
            if decision in {
                "ORDER_CONFIRMED",
                "AFFIRM_CONFIRMED",
                "DENY_CONFIRMED",
                "CANCEL_ORDER",
            }:
                self.stt_retry_count = 0

        self.publish_action(action)
        self.publish_head_command(action.get("head", "CENTER"))

        if should_listen and not str(action.get("tts") or "").strip():
            self.trigger_pending_stt("empty_tts")

    def decision_callback(self, msg):
        """Alias used by existing callback tests."""
        self.response_callback(msg)

    def stt_status_callback(self, msg):
        status = msg.data.strip()

        if status in {"ready", "recording", "transcribing", "done"}:
            return
        if status.startswith("error") or status in {"empty", "too_quiet", "rejected"}:
            # Wake-gate captures have no pending ActionNode listen token.
            if not self._listen_pending:
                return
            self.handle_stt_failed(status)

    def tts_status_callback(self, msg):
        status = msg.data.strip()
        if status == "speaking":
            with self._listen_lock:
                if self._listen_pending:
                    self._listen_seen_speaking = True
            return

        if status == "done":
            if self._guide_head_active:
                self._guide_head_active = False
                self.publish_head_command("CENTER")

            with self._listen_lock:
                should_trigger = self._listen_pending and self._listen_seen_speaking
            if should_trigger:
                self.trigger_pending_stt("tts_done")
            return

        if status.startswith("error"):
            if self._guide_head_active:
                self._guide_head_active = False
                self.publish_head_command("CENTER")
            self.get_logger().warning(
                f"TTS failed while waiting to listen: {status}"
            )
            self.trigger_pending_stt("tts_error")

    def handle_stt_failed(self, status):
        if self.stt_retry_count >= self.max_stt_retries:
            self.cancel_pending_listen()
            self.publish_response_request({
                "decision": "STT_FAILED",
                "response_key": "stt_failed",
                "response_args": {"status": status},
                "reason": status,
                "state": "STT_FAILED",
            })
            self.get_logger().warning("STT failed too many times. Stop retrying.")
            return

        self.stt_retry_count += 1
        self.publish_response_request({
            "decision": "STT_RETRY",
            "response_key": "stt_retry",
            "response_args": {
                "status": status,
                "retry_count": self.stt_retry_count,
                "max_retries": self.max_stt_retries,
            },
            "reason": status,
            "state": "STT_RETRY",
        })

    def arm_listen_after_tts(self, source):
        with self._listen_lock:
            self._listen_token += 1
            token = self._listen_token
            self._listen_pending = True
            self._listen_seen_speaking = False

        threading.Thread(
            target=self.listen_timeout_worker,
            args=(token, source),
            daemon=True,
        ).start()
        self.get_logger().info(
            f"Waiting for TTS completion before STT: source={source}, token={token}"
        )

    def listen_timeout_worker(self, token, source):
        time.sleep(self.tts_done_timeout_sec)
        with self._listen_lock:
            timed_out = self._listen_pending and self._listen_token == token
        if timed_out:
            self.get_logger().warning(
                "TTS completion timeout. Starting STT through fallback: "
                f"source={source}, token={token}"
            )
            self.trigger_pending_stt("tts_timeout")

    def trigger_pending_stt(self, reason):
        with self._listen_lock:
            if not self._listen_pending:
                return
            self._listen_pending = False
            self._listen_seen_speaking = False

        msg = String()
        msg.data = "start"
        self.stt_trigger_publisher.publish(msg)
        self.get_logger().info(f"Published STT trigger: start ({reason})")

    def cancel_pending_listen(self):
        with self._listen_lock:
            self._listen_token += 1
            self._listen_pending = False
            self._listen_seen_speaking = False

    def publish_response_request(self, request):
        ros_msg = String()
        ros_msg.data = json.dumps(request, ensure_ascii=False)
        self.response_request_publisher.publish(ros_msg)
        self.get_logger().info(f"Published response request: {ros_msg.data}")

    def publish_action(self, action):
        ros_msg = String()
        ros_msg.data = json.dumps(action, ensure_ascii=False)
        self.publisher.publish(ros_msg)
        self.get_logger().info(f"Published action : {ros_msg.data}")

    def publish_head_command(self, head):
        command = str(head or "CENTER").upper()
        if self._guide_head_active and command not in {"CENTER", "TURN_LEFT", "TURN_RIGHT"}:
            self.get_logger().info(
                f"Ignoring head command {command} while GUIDE direction is held."
            )
            return

        if command in {"TURN_LEFT", "TURN_RIGHT"}:
            self._guide_head_active = True

        ros_msg = String()
        ros_msg.data = command
        self.motor_command_publisher.publish(ros_msg)
        self.get_logger().info(f"Published motor command: {command}")

    def make_action(self, response_result):
        decision = response_result.get("decision", "UNKNOWN")
        speech = str(response_result.get("speech") or "")
        display_text = str(response_result.get("display_text") or speech)
        reason = response_result.get("reason", "")
        rule = self.get_action_rule(response_result)

        return {
            "decision": decision,
            "tts": speech,
            "face": rule["face"],
            "display": rule["display"],
            "display_text": display_text,
            "head": rule["head"],
            "arm": rule["arm"],
            "priority": rule["priority"],
            "source_reason": reason,
            "raw_response": response_result,
        }

    def make_error_action(self, reason, raw_message=""):
        return {
            "decision": "ACTION_ERROR",
            "tts": "처리 중 오류가 발생했습니다.",
            "face": "ERROR",
            "display": "ERROR",
            "display_text": "처리 오류",
            "head": "CENTER",
            "arm": "WAIT",
            "priority": "HIGH",
            "source_reason": reason,
            "raw_decision": {"raw_message": raw_message},
        }

    def get_action_rule(self, response_result):
        decision = response_result.get("decision", "UNKNOWN")
        ask_rule = {
            "face": "QUESTION",
            "display": "ASK_AGAIN",
            "head": "CENTER",
            "arm": "WAIT",
            "priority": "HIGH",
        }
        error_rule = {
            "face": "ERROR",
            "display": "ERROR",
            "head": "LOOK_USER",
            "arm": "WAIT",
            "priority": "HIGH",
        }
        base_rules = {
            "START_ORDER": {
                "face": "SMILE",
                "display": "GREETING",
                "head": "NOD",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "REPROMPT": ask_rule,
            "ASK_MENU": {**ask_rule, "display": "ASK_MENU"},
            "ASK_TEMPERATURE": {**ask_rule, "display": "ASK_TEMPERATURE"},
            "ASK_QUANTITY": {**ask_rule, "display": "ASK_QUANTITY"},
            "OUT_OF_POLICY": {**ask_rule, "display": "ORDER_HELP"},
            "CONFIRM_ITEM": {
                "face": "SMILE",
                "display": "ITEM_CONFIRM",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "CONFIRM_ORDER": {
                "face": "SMILE",
                "display": "ORDER_CONFIRM",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "ORDER_CONFIRMED": {
                "face": "HAPPY",
                "display": "ORDER_ACCEPTED",
                "head": "DOUBLE_NOD",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "REORDER_REQUEST": {**ask_rule, "display": "ORDER_RETRY"},
            "MODIFY_ORDER": {
                **ask_rule,
                "display": "MODIFY_ORDER",
                "head": "SHAKE",
            },
            "GUIDE_CUSTOMER": self.make_guide_rule(response_result),
            "PREORDER_STATUS": {
                "face": "SMILE",
                "display": "ORDER_STATUS",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "PAYMENT_GUIDE": {
                "face": "SMILE",
                "display": "PAYMENT_GUIDE",
                "head": "CENTER",
                "arm": "POINT_DISPLAY",
                "priority": "NORMAL",
            },
            "CANCEL_ORDER": {
                "face": "NEUTRAL",
                "display": "CANCEL_ORDER",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "HIGH",
            },
            "AFFIRM_CONFIRMED": {
                "face": "HAPPY",
                "display": "ORDER_ACCEPTED",
                "head": "DOUBLE_NOD",
                "arm": "WAIT",
                "priority": "NORMAL",
            },
            "DENY_CONFIRMED": {
                **ask_rule,
                "display": "ORDER_RETRY",
                "head": "SHAKE",
            },
            "STT_RETRY": {
                **ask_rule,
                "display": "ASK_AGAIN",
                "head": "SHAKE",
                "arm": "UNSURE",
            },
            "STT_FAILED": {**error_rule, "display": "STT_FAILED"},
            "RESPONSE_ERROR": error_rule,
            "UNKNOWN": {
                "face": "QUESTION",
                "display": "HELP",
                "head": "CENTER",
                "arm": "WAIT",
                "priority": "LOW",
            },
        }
        return base_rules.get(decision, base_rules["UNKNOWN"])

    def make_guide_rule(self, response_result):
        direction = self.extract_direction(response_result)
        if direction == "LEFT":
            return {
                "face": "SMILE",
                "display": "GUIDE_LEFT",
                "head": "TURN_LEFT",
                "arm": "POINT_LEFT",
                "priority": "NORMAL",
            }
        if direction == "RIGHT":
            return {
                "face": "SMILE",
                "display": "GUIDE_RIGHT",
                "head": "TURN_RIGHT",
                "arm": "POINT_RIGHT",
                "priority": "NORMAL",
            }
        return {
            "face": "SMILE",
            "display": "GUIDE",
            "head": "CENTER",
            "arm": "POINT_DISPLAY",
            "priority": "NORMAL",
        }

    def extract_direction(self, response_result):
        response_args = response_result.get("response_args") or {}
        direction = response_args.get("direction") if isinstance(response_args, dict) else None
        if not direction:
            direction = response_result.get("direction")
        if not direction:
            direction = response_result.get("nlu_result", {}).get("direction")
        if isinstance(direction, str):
            direction = direction.upper()
        return direction if direction in ["LEFT", "RIGHT"] else None


class _OrderHandoffActionMixin:
    """Action node variant for post-order handoff and persistent ROS VAD retries."""

    LISTEN_AFTER_TTS_DECISIONS = _CoreActionNode.LISTEN_AFTER_TTS_DECISIONS | {
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
        """Stop automatic retries on an STT runtime error."""
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
            # Wake-gate captures are started directly by the decision node, so
            # the action node has no pending listen token for them. Stay silent
            # and let the wake gate re-arm instead of emitting STT_RETRY actions.
            if not self._listen_pending:
                return
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


class ActionNode(_OrderHandoffActionMixin, _CoreActionNode):
    """ROS2 action node for robot responses and STT retry handling."""


def main(args=None):
    rclpy.init(args=args)
    node = ActionNode()
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