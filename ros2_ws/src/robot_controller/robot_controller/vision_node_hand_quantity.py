from __future__ import annotations

import os
import time

import cv2
import rclpy
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String

from .hand_quantity_gesture import HandQuantityGestureRecognizer
from .head_gesture_frame_estimator import GestureFrame, HeadGestureFrameEstimator
from .head_gesture_recognizer import HeadGestureRecognizer
from .vision_node import VisionNode


class SensitiveShakeRecognizer(HeadGestureRecognizer):
    """Detect natural NOD/SHAKE while giving NOD explicit priority.

    SHAKE keeps the tuned one-reversal, balanced-travel detector unchanged.
    NOD confirms as soon as a strong vertical excursion shows a real direction
    reversal instead of waiting for a fuller return toward neutral. Vertical
    range and motion must still dominate horizontal motion, preventing the fast
    NOD rule from stealing a real SHAKE.
    """

    # SHAKE: frozen at the last good physical-test values.
    SHAKE_WINDOW_SECONDS = 1.05
    SHAKE_MIN_X_RANGE = 0.030
    SHAKE_MIN_X_MOTION = 0.055
    SHAKE_X_TO_Y_RANGE_RATIO = 1.25
    SHAKE_DIRECTION_EPSILON = 0.004
    SHAKE_MIN_REVERSALS = 1
    SHAKE_MIN_YAW_RANGE_DEG = 6.0
    SHAKE_MIN_LEG_TRAVEL = 0.015
    SHAKE_MIN_LEG_BALANCE = 0.45
    SHAKE_MIN_MOTION_RANGE_RATIO = 1.40
    SHAKE_YAW_TO_PITCH_RANGE_RATIO = 1.20
    SHAKE_YAW_TO_PITCH_MOTION_RATIO = 1.10

    # NOD-only tuning. SHAKE values above must remain unchanged.
    NOD_WINDOW_SECONDS = 0.50
    NOD_MIN_Y_RANGE = 0.030
    NOD_Y_TO_X_RANGE_RATIO = 1.15
    NOD_Y_TO_X_MOTION_RATIO = 1.05
    NOD_DIRECTION_EPSILON = 0.002
    NOD_MIN_OUTBOUND_TRAVEL = 0.020
    NOD_MIN_RETURN_TRAVEL = 0.004

    # Prevent SHAKE from firing while a vertical nod is still developing.
    NOD_GUARD_MIN_Y_RANGE = 0.026
    NOD_GUARD_Y_TO_X_RATIO = 1.00

    def __init__(self, config=None) -> None:
        super().__init__(config=config)
        self.last_shake_metrics: dict[str, float | int] | None = None
        self.last_nod_metrics: dict[str, float | int] | None = None

    @classmethod
    def _strongest_reversal_legs(cls, values: list[float]) -> tuple[float, float]:
        """Return strongest opposite-direction travel before/after one turn."""
        best_first = 0.0
        best_second = 0.0
        best_score = 0.0

        for turn_index in range(1, len(values) - 1):
            turn_value = values[turn_index]
            for start_index in range(turn_index):
                first_delta = turn_value - values[start_index]
                if abs(first_delta) < cls.SHAKE_DIRECTION_EPSILON:
                    continue
                for end_index in range(turn_index + 1, len(values)):
                    second_delta = values[end_index] - turn_value
                    if abs(second_delta) < cls.SHAKE_DIRECTION_EPSILON:
                        continue
                    if first_delta * second_delta >= 0.0:
                        continue

                    first_leg = abs(first_delta)
                    second_leg = abs(second_delta)
                    score = min(first_leg, second_leg)
                    if score > best_score:
                        best_score = score
                        best_first = first_leg
                        best_second = second_leg

        return best_first, best_second

    @classmethod
    def _strongest_nod_reversal_legs(
        cls,
        values: list[float],
    ) -> tuple[float, float]:
        """Find a vertical outbound leg followed by a meaningful return leg."""
        best_first = 0.0
        best_second = 0.0
        best_score = 0.0

        for turn_index in range(1, len(values) - 1):
            turn_value = values[turn_index]
            for start_index in range(turn_index):
                first_delta = turn_value - values[start_index]
                if abs(first_delta) < cls.NOD_DIRECTION_EPSILON:
                    continue
                for end_index in range(turn_index + 1, len(values)):
                    second_delta = values[end_index] - turn_value
                    if abs(second_delta) < cls.NOD_DIRECTION_EPSILON:
                        continue
                    if first_delta * second_delta >= 0.0:
                        continue

                    first_leg = abs(first_delta)
                    second_leg = abs(second_delta)
                    score = first_leg + second_leg
                    if score > best_score:
                        best_score = score
                        best_first = first_leg
                        best_second = second_leg

        return best_first, best_second

    def _nod_window_metrics(self, samples):
        latest = samples[-1].timestamp
        nod_cutoff = latest - self.NOD_WINDOW_SECONDS
        nod_window = [sample for sample in samples if sample.timestamp >= nod_cutoff]
        if len(nod_window) < self.config.landmark_min_samples:
            return None

        xs = [float(sample.nose_rel_x) for sample in nod_window]
        ys = [float(sample.nose_rel_y) for sample in nod_window]
        return {
            "xs": xs,
            "ys": ys,
            "x_range": max(xs) - min(xs),
            "y_range": max(ys) - min(ys),
            "x_motion": self._value_motion(xs),
            "y_motion": self._value_motion(ys),
        }

    def _detect_relaxed_nod_first(self, samples) -> bool:
        self.last_nod_metrics = None
        metrics = self._nod_window_metrics(samples)
        if metrics is None:
            return False

        first_leg, second_leg = self._strongest_nod_reversal_legs(metrics["ys"])
        has_vertical_reversal = (
            first_leg >= self.NOD_MIN_OUTBOUND_TRAVEL
            and second_leg >= self.NOD_MIN_RETURN_TRAVEL
        )

        detected = (
            metrics["y_range"] >= self.NOD_MIN_Y_RANGE
            and metrics["y_range"]
            >= metrics["x_range"] * self.NOD_Y_TO_X_RANGE_RATIO
            and metrics["y_motion"]
            >= metrics["x_motion"] * self.NOD_Y_TO_X_MOTION_RATIO
            and has_vertical_reversal
        )
        if detected:
            self.last_nod_metrics = {
                "x_range": metrics["x_range"],
                "y_range": metrics["y_range"],
                "x_motion": metrics["x_motion"],
                "y_motion": metrics["y_motion"],
                "first_leg": first_leg,
                "second_leg": second_leg,
            }
        return detected

    def _has_developing_nod_evidence(self, samples) -> bool:
        metrics = self._nod_window_metrics(samples)
        if metrics is None:
            return False
        return (
            metrics["y_range"] >= self.NOD_GUARD_MIN_Y_RANGE
            and metrics["y_range"]
            >= metrics["x_range"] * self.NOD_GUARD_Y_TO_X_RATIO
        )

    def _detect_landmark_gesture(self, samples):
        self.last_shake_metrics = None
        self.last_nod_metrics = None

        # NOD is the higher-priority confirmation gesture. Confirm on a real
        # vertical direction reversal instead of waiting for a fuller neutral return.
        if self._detect_relaxed_nod_first(samples):
            return self.NOD

        # A developing vertical motion should wait for a possible NOD rather than
        # being prematurely interpreted as SHAKE.
        if self._has_developing_nod_evidence(samples):
            return self.NONE

        latest = samples[-1].timestamp
        shake_cutoff = latest - self.SHAKE_WINDOW_SECONDS
        shake_window = [
            sample for sample in samples if sample.timestamp >= shake_cutoff
        ]

        if len(shake_window) >= self.config.landmark_min_samples:
            xs = [float(sample.nose_rel_x) for sample in shake_window]
            ys = [float(sample.nose_rel_y) for sample in shake_window]
            yaws = [float(sample.yaw) for sample in shake_window]
            pitches = [float(sample.pitch) for sample in shake_window]

            x_range = max(xs) - min(xs)
            y_range = max(ys) - min(ys)
            x_motion = self._value_motion(xs)
            yaw_range = max(yaws) - min(yaws)
            pitch_range = max(pitches) - min(pitches)
            yaw_motion = self._value_motion(yaws)
            pitch_motion = self._value_motion(pitches)
            reversals = self._count_direction_reversals(
                xs,
                self.SHAKE_DIRECTION_EPSILON,
            )
            first_leg, second_leg = self._strongest_reversal_legs(xs)

            max_leg = max(first_leg, second_leg)
            leg_balance = min(first_leg, second_leg) / max_leg if max_leg > 0.0 else 0.0
            motion_range_ratio = x_motion / x_range if x_range > 0.0 else 0.0

            enough_horizontal_travel = (
                x_range >= self.SHAKE_MIN_X_RANGE
                and x_motion >= self.SHAKE_MIN_X_MOTION
            )
            horizontally_dominant = (
                x_range >= y_range * self.SHAKE_X_TO_Y_RANGE_RATIO
            )
            has_direction_change = reversals >= self.SHAKE_MIN_REVERSALS
            has_two_strong_legs = (
                first_leg >= self.SHAKE_MIN_LEG_TRAVEL
                and second_leg >= self.SHAKE_MIN_LEG_TRAVEL
            )
            has_balanced_reversal = leg_balance >= self.SHAKE_MIN_LEG_BALANCE
            has_real_back_and_forth = (
                motion_range_ratio >= self.SHAKE_MIN_MOTION_RANGE_RATIO
            )
            has_real_yaw_support = yaw_range >= self.SHAKE_MIN_YAW_RANGE_DEG
            yaw_range_dominates_pitch = (
                yaw_range
                >= pitch_range * self.SHAKE_YAW_TO_PITCH_RANGE_RATIO
            )
            yaw_motion_dominates_pitch = (
                yaw_motion
                >= pitch_motion * self.SHAKE_YAW_TO_PITCH_MOTION_RATIO
            )

            if (
                enough_horizontal_travel
                and horizontally_dominant
                and has_direction_change
                and has_two_strong_legs
                and has_balanced_reversal
                and has_real_back_and_forth
                and has_real_yaw_support
                and yaw_range_dominates_pitch
                and yaw_motion_dominates_pitch
            ):
                self.last_shake_metrics = {
                    "x_range": x_range,
                    "x_motion": x_motion,
                    "y_range": y_range,
                    "yaw_range": yaw_range,
                    "pitch_range": pitch_range,
                    "yaw_motion": yaw_motion,
                    "pitch_motion": pitch_motion,
                    "reversals": reversals,
                    "first_leg": first_leg,
                    "second_leg": second_leg,
                    "leg_balance": leg_balance,
                    "motion_range_ratio": motion_range_ratio,
                }
                return self.SHAKE

        # Preserve main's strict detector only as a final fallback.
        return super()._detect_landmark_gesture(samples)


class HandQuantityVisionNode(VisionNode):
    """VisionNode extension that adds hand quantity and tuned head gestures."""

    NOD_CANDIDATE_HOLD_SEC = 0.05
    SHAKE_CANDIDATE_HOLD_SEC = 0.25

    def __init__(self) -> None:
        os.environ.setdefault("PUMPKIN_GESTURE_CANDIDATE_HOLD_SEC", "0.25")
        super().__init__()

        if self.head_gesture_recognizer is not None:
            self.head_gesture_recognizer = SensitiveShakeRecognizer()

        self.robot_gesture_hold_sec = max(
            0.0,
            float(os.getenv("PUMPKIN_ROBOT_GESTURE_HOLD_SEC", "2.0")),
        )

        self.hand_gesture_pub = self.create_publisher(
            String,
            "/user/hand_gesture",
            10,
        )
        self.hand_quantity_recognizer = None

        if os.getenv("PUMPKIN_ENABLE_HAND_QUANTITY", "1") == "1":
            try:
                self.hand_quantity_recognizer = HandQuantityGestureRecognizer(
                    hold_sec=float(
                        os.getenv("PUMPKIN_HAND_GESTURE_HOLD_SEC", "0.35")
                    ),
                    min_frames=int(
                        os.getenv("PUMPKIN_HAND_GESTURE_MIN_FRAMES", "3")
                    ),
                    extension_ratio=float(
                        os.getenv("PUMPKIN_HAND_EXTENSION_RATIO", "1.15")
                    ),
                    min_hand_span=float(
                        os.getenv("PUMPKIN_HAND_MIN_SPAN", "0.12")
                    ),
                )
                self.get_logger().info(
                    "Hand quantity recognition enabled: "
                    "/user/hand_gesture (ONE_FINGER..FIVE_FINGERS -> quantity 1..5)"
                )
            except RuntimeError as exc:
                self.get_logger().warning(
                    "Hand quantity recognition disabled; ordinary vision and "
                    f"ordering will continue: {exc}"
                )
        else:
            self.get_logger().info(
                "Hand quantity recognition disabled by PUMPKIN_ENABLE_HAND_QUANTITY=0"
            )

        self.get_logger().info(
            "Relaxed multimodal head-gesture arbitration enabled: "
            f"nod_hold={self.NOD_CANDIDATE_HOLD_SEC:.2f}s, "
            f"shake_hold={self.SHAKE_CANDIDATE_HOLD_SEC:.2f}s, "
            f"robot_gesture_hold={self.robot_gesture_hold_sec:.2f}s, "
            "speech_detected does not reset NOD/SHAKE recognition"
        )
        self.get_logger().warning(
            "NOD-priority gesture mode: fast vertical-reversal NOD + preserved "
            "STT listening evidence; SHAKE thresholds remain frozen"
        )

    def timer_callback(self) -> None:
        """Run the existing vision flow plus hand recognition on one camera frame."""
        ret, frame = self.cap.read()
        if not ret:
            now = time.monotonic()
            if now - self.last_frame_warning_time >= 5.0:
                self.get_logger().warning("Camera frame read failed.")
                self.last_frame_warning_time = now
            return

        gesture_frame = None
        mediapipe_face_detected = False
        if self.head_gesture_estimator is not None:
            gesture_frame = self.head_gesture_estimator.estimate(frame)
            mediapipe_face_detected = (
                self.head_gesture_estimator.status
                != HeadGestureFrameEstimator.FACE_NOT_DETECTED
            )

        frame_height, frame_width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(self.min_face_width, self.min_face_height),
        )

        valid_faces = self.filter_valid_faces(faces, frame_width, frame_height)
        haar_face_detected = len(valid_faces) > 0
        has_face = haar_face_detected or mediapipe_face_detected

        changed = self.update_person_state(has_face)
        self.process_face_recognition(frame, has_face)
        if changed:
            self.publish_presence(force=True)
            if not self.person_detected:
                self.reset_head_gesture_state()
                self.reset_hand_quantity_state()
                if self.face_recognizer is not None:
                    self.face_recognizer.reset()
        elif time.monotonic() - self.last_presence_publish_time >= self.presence_heartbeat_sec:
            self.publish_presence(force=True, heartbeat=True)

        self.log_detection_probe(
            haar_faces=len(valid_faces),
            mediapipe_face=mediapipe_face_detected,
        )

        if gesture_frame is not None:
            self.process_head_gesture_frame(gesture_frame)

        now = time.monotonic()
        self.process_hand_quantity_gesture(frame, now)
        self.maybe_publish_pending_gesture(now)
        self.publish_demo_frame(frame)

    def process_head_gesture_frame(self, gesture_frame: GestureFrame) -> None:
        """Track NOD/SHAKE even while STT is recording."""
        if self.head_gesture_recognizer is None:
            return

        now = time.monotonic()
        if (
            self.tts_speaking
            or self.robot_turn_active
            or now < self.gesture_suppress_until
        ):
            self.cancel_pending_gesture("gesture_suppressed")
            self.head_gesture_recognizer.reset()
            return

        gesture = self.head_gesture_recognizer.add_sample(
            timestamp=now,
            pitch=gesture_frame.pitch,
            yaw=gesture_frame.yaw,
            nose_rel_x=gesture_frame.nose_rel_x,
            nose_rel_y=gesture_frame.nose_rel_y,
        )
        if gesture not in {
            HeadGestureRecognizer.NOD,
            HeadGestureRecognizer.SHAKE,
        }:
            return

        if (
            gesture == HeadGestureRecognizer.NOD
            and isinstance(self.head_gesture_recognizer, SensitiveShakeRecognizer)
            and self.head_gesture_recognizer.last_nod_metrics is not None
        ):
            metrics = self.head_gesture_recognizer.last_nod_metrics
            self.get_logger().info(
                "NOD evidence: "
                f"y_range={metrics['y_range']:.4f}, "
                f"y_motion={metrics['y_motion']:.4f}, "
                f"x_range={metrics['x_range']:.4f}, "
                f"x_motion={metrics['x_motion']:.4f}, "
                f"outbound={metrics['first_leg']:.4f}, "
                f"return={metrics['second_leg']:.4f}"
            )

        if (
            gesture == HeadGestureRecognizer.SHAKE
            and isinstance(self.head_gesture_recognizer, SensitiveShakeRecognizer)
            and self.head_gesture_recognizer.last_shake_metrics is not None
        ):
            metrics = self.head_gesture_recognizer.last_shake_metrics
            self.get_logger().info(
                "SHAKE evidence: "
                f"x_range={metrics['x_range']:.4f}, "
                f"x_motion={metrics['x_motion']:.4f}, "
                f"y_range={metrics['y_range']:.4f}, "
                f"yaw_range={metrics['yaw_range']:.2f}, "
                f"pitch_range={metrics['pitch_range']:.2f}, "
                f"yaw_motion={metrics['yaw_motion']:.2f}, "
                f"pitch_motion={metrics['pitch_motion']:.2f}, "
                f"reversals={int(metrics['reversals'])}, "
                f"leg1={metrics['first_leg']:.4f}, "
                f"leg2={metrics['second_leg']:.4f}, "
                f"leg_balance={metrics['leg_balance']:.2f}, "
                f"motion_range={metrics['motion_range_ratio']:.2f}"
            )

        self.queue_gesture_candidate(gesture, now)

    def queue_gesture_candidate(self, gesture: str, now: float) -> None:
        """Give the higher-priority NOD a shorter confirmation hold."""
        hold_sec = (
            self.NOD_CANDIDATE_HOLD_SEC
            if gesture == HeadGestureRecognizer.NOD
            else self.SHAKE_CANDIDATE_HOLD_SEC
        )
        self.pending_gesture = gesture
        self.pending_gesture_deadline = now + hold_sec
        self.get_logger().info(
            "Head gesture candidate detected: "
            f"{gesture}; waiting {hold_sec:.2f}s before confirming"
        )

    def maybe_publish_pending_gesture(self, now: float) -> None:
        """Publish a stable visual answer without a hard voice-turn veto."""
        gesture = self.pending_gesture
        if gesture not in {
            HeadGestureRecognizer.NOD,
            HeadGestureRecognizer.SHAKE,
        }:
            return

        if (
            self.tts_speaking
            or self.robot_turn_active
            or now < self.gesture_suppress_until
        ):
            self.cancel_pending_gesture("robot_or_grace_suppression")
            return
        if now < self.pending_gesture_deadline:
            return

        self.pending_gesture = None
        self.pending_gesture_deadline = 0.0
        msg = String()
        msg.data = gesture
        self._publish_if_active(self.gesture_pub, msg)
        self.get_logger().info(
            f"Published confirmed user head gesture: {gesture} after multimodal hold"
        )

    def stt_status_callback(self, msg: String) -> None:
        """Keep voice state for diagnostics without erasing head-gesture evidence."""
        status = str(msg.data or "").strip().lower()

        if status in {"speech_detected", "recording", "transcribing"}:
            if not self.voice_turn_active:
                self.get_logger().info(
                    f"Voice activity detected alongside vision: stt_status={status}"
                )
            self.voice_turn_active = True
            return

        if status == "done" and self.voice_turn_active:
            return

        if status == "listening":
            # TTS completion already reset stale robot-turn evidence. Do not reset
            # again here: a short customer NOD may begin immediately as listening
            # starts, and throwing those first frames away delays recognition.
            self.voice_turn_active = False
            return

        if (
            status in {
                "ready",
                "cancelled",
                "empty",
                "no_speech",
                "too_quiet",
                "rejected",
            }
            or status.startswith("error")
        ):
            self.voice_turn_active = False
            self.cancel_pending_gesture(f"stt_{status}")
            self.reset_head_gesture_recognizer_only()

    def process_hand_quantity_gesture(self, frame, now: float) -> None:
        recognizer = self.hand_quantity_recognizer
        if recognizer is None:
            return

        if (
            self.tts_speaking
            or self.robot_turn_active
            or self.voice_turn_active
            or now < self.gesture_suppress_until
        ):
            recognizer.reset()
            return

        gesture = recognizer.process(frame, timestamp=now)
        if gesture not in {
            HandQuantityGestureRecognizer.ONE_FINGER,
            HandQuantityGestureRecognizer.TWO_FINGERS,
            HandQuantityGestureRecognizer.THREE_FINGERS,
            HandQuantityGestureRecognizer.FOUR_FINGERS,
            HandQuantityGestureRecognizer.FIVE_FINGERS,
        }:
            return

        msg = String()
        msg.data = gesture
        if self._publish_if_active(self.hand_gesture_pub, msg):
            self.get_logger().info(
                f"Published confirmed user hand gesture: {gesture}"
            )

    def reset_hand_quantity_state(self) -> None:
        if self.hand_quantity_recognizer is not None:
            self.hand_quantity_recognizer.reset()

    def destroy_node(self) -> None:
        if self.hand_quantity_recognizer is not None:
            self.hand_quantity_recognizer.close()
            self.hand_quantity_recognizer = None
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = HandQuantityVisionNode()
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