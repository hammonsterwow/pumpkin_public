import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, String

from .head_gesture_frame_estimator import GestureFrame, HeadGestureFrameEstimator
from .head_gesture_recognizer import HeadGestureRecognizer

from .hand_quantity_gesture import HandQuantityGestureRecognizer


class _CoreVisionNode(Node):
    def __init__(self):
        super().__init__("vision_node")

        self.person_pub = self.create_publisher(Bool, "/human_presence", 10)
        self.gesture_pub = self.create_publisher(String, "/user/head_gesture", 10)
        self.face_recognition_pub = self.create_publisher(
            String, "/face_recognition_result", 10
        )

        demo_camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.demo_camera_pub = self.create_publisher(
            CompressedImage,
            "/demo/camera/compressed",
            demo_camera_qos,
        )
        self.demo_stream_fps = max(
            1.0,
            float(os.getenv("PUMPKIN_DEMO_STREAM_FPS", "8.0")),
        )
        self.demo_stream_width = max(
            320,
            int(os.getenv("PUMPKIN_DEMO_STREAM_WIDTH", "640")),
        )
        self.demo_stream_jpeg_quality = min(
            90,
            max(40, int(os.getenv("PUMPKIN_DEMO_STREAM_JPEG_QUALITY", "68"))),
        )
        self.last_demo_frame_time = 0.0

        self.create_subscription(String, "/tts/status", self.tts_status_callback, 10)
        self.create_subscription(String, "/stt/status", self.stt_status_callback, 10)
        self.create_subscription(String, "/motor_command", self.motor_command_callback, 10)

        self.camera_index = int(os.getenv("PUMPKIN_CAMERA_INDEX", "0"))
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            self.get_logger().error(
                f"Camera {self.camera_index} open failed. "
                "Set PUMPKIN_CAMERA_INDEX to an available video device index."
            )
        else:
            self.get_logger().info(
                f"Camera {self.camera_index} opened successfully."
            )

        cascade_path = self.find_haarcascade_path()
        if cascade_path is None:
            self.get_logger().error(
                "Haar cascade file not found. Install python3-opencv or opencv-data."
            )
            raise RuntimeError("haarcascade_frontalface_default.xml not found")

        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            raise RuntimeError("Failed to load Haar cascade file")

        self.face_recognizer = None
        self.face_recognition_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="pumpkin-face-recognition",
        )
        self.face_recognition_future = None
        if os.getenv("PUMPKIN_ENABLE_FACE_RECOGNITION", "0") == "1":
            try:
                from .realtime_face_recognition import RealtimeFaceRecognizer

                self.face_recognizer = RealtimeFaceRecognizer()
                self.get_logger().info(
                    "Realtime buffalo_l face recognition enabled."
                )
            except Exception as exc:
                self.get_logger().error(
                    "Realtime face recognition disabled; ordinary vision/order "
                    f"flow will continue: {exc}"
                )

        self.person_detected = False
        self.consecutive_face_frames = 0
        self.consecutive_no_face_frames = 0

        self.required_face_frames = 3
        self.required_no_face_frames = 50
        self.min_face_width = 70
        self.min_face_height = 70
        self.max_face_area_ratio = 0.80

        self.last_published_presence = None
        self.last_presence_publish_time = 0.0
        self.presence_heartbeat_sec = 1.0
        self.last_frame_warning_time = 0.0
        self.last_detection_debug_time = 0.0

        self.tts_speaking = False
        self.robot_turn_active = False
        self.gesture_suppress_until = 0.0
        self.robot_gesture_hold_sec = 3.0
        self.robot_settle_sec = 0.45

        # A detected customer gesture is only a candidate at first. Keep a short
        # voice-veto window so a natural face/head movement just before speech
        # cannot immediately steal the confirmation turn from STT.
        self.gesture_candidate_hold_sec = max(
            0.0,
            float(os.getenv("PUMPKIN_GESTURE_CANDIDATE_HOLD_SEC", "0.50")),
        )
        # After robot speech ends, give the customer a brief chance to start
        # speaking before visual confirmation is allowed to become a candidate.
        self.response_gesture_grace_sec = max(
            0.0,
            float(os.getenv("PUMPKIN_GESTURE_RESPONSE_GRACE_SEC", "0.50")),
        )
        self.pending_gesture = None
        self.pending_gesture_deadline = 0.0
        # Once real speech begins, voice owns the turn through STT/NLU/Decision.
        # It is released when the robot starts its next TTS or a new listen turn
        # begins. This prevents a late gesture from overtaking a transcribing or
        # NLU-processing voice answer.
        self.voice_turn_active = False

        self.head_gesture_estimator = None
        self.head_gesture_recognizer = None
        try:
            self.head_gesture_estimator = HeadGestureFrameEstimator()
            self.head_gesture_recognizer = HeadGestureRecognizer()
            self.get_logger().info(
                "Head gesture recognition enabled: /user/head_gesture"
            )
        except RuntimeError as exc:
            self.get_logger().warning(
                "Head gesture recognition disabled; presence detection will continue: "
                f"{exc}"
            )

        self.timer = self.create_timer(0.1, self.timer_callback)

        self.publish_presence(force=True)
        self.get_logger().info(
            "vision_node started with Haar + MediaPipe presence detection and "
            "user head gesture recognition (10 FPS)."
        )
        self.get_logger().info(
            "Gesture arbitration enabled: "
            f"candidate_hold={self.gesture_candidate_hold_sec:.2f}s, "
            f"response_grace={self.response_gesture_grace_sec:.2f}s, "
            "speech_detected=voice priority"
        )
        self.get_logger().info(
            "Demo camera publisher ready: /demo/camera/compressed; "
            f"{self.demo_stream_width}px, {self.demo_stream_fps:.1f} FPS, "
            f"JPEG quality={self.demo_stream_jpeg_quality}. "
            "JPEG encoding is skipped when no demo subscriber is connected."
        )

    def find_haarcascade_path(self):
        candidates = []
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            candidates.append(
                os.path.join(
                    cv2.data.haarcascades,
                    "haarcascade_frontalface_default.xml",
                )
            )

        candidates.extend([
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/local/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        ])

        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def timer_callback(self):
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
                if self.face_recognizer is not None:
                    self.face_recognizer.reset()
        elif time.monotonic() - self.last_presence_publish_time >= self.presence_heartbeat_sec:
            # ROS 2 discovery can take longer than the initial False -> True
            # transition when vision_node starts. Re-publish the current state so
            # a late-matched Decision subscriber still receives the active user.
            self.publish_presence(force=True, heartbeat=True)

        self.log_detection_probe(
            haar_faces=len(valid_faces),
            mediapipe_face=mediapipe_face_detected,
        )

        if gesture_frame is not None:
            self.process_head_gesture_frame(gesture_frame)

        self.maybe_publish_pending_gesture(time.monotonic())
        self.publish_demo_frame(frame)

    def _publish_if_active(self, publisher, message) -> bool:
        """Avoid a shutdown race between a timer callback and ROS context teardown."""
        if not rclpy.ok():
            return False
        try:
            publisher.publish(message)
        except Exception:
            if not rclpy.ok():
                return False
            raise
        return True

    def publish_demo_frame(self, frame):
        """Publish a small annotated JPEG only while the demo bridge is connected.

        The camera is not opened a second time and MediaPipe is not executed a
        second time. The six yellow points come from the same FaceMesh result
        already used by the head-gesture estimator.
        """

        if self.demo_camera_pub.get_subscription_count() < 1:
            return

        now = time.monotonic()
        if now - self.last_demo_frame_time < 1.0 / self.demo_stream_fps:
            return
        self.last_demo_frame_time = now

        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            return

        scale = min(1.0, self.demo_stream_width / float(width))
        if scale < 1.0:
            target = (
                self.demo_stream_width,
                max(1, int(round(height * scale))),
            )
            demo_frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        else:
            demo_frame = frame.copy()

        if self.head_gesture_estimator is not None:
            display_landmarks = self.head_gesture_estimator.display_landmarks
        else:
            display_landmarks = ()

        demo_height, demo_width = demo_frame.shape[:2]
        for rel_x, rel_y in display_landmarks:
            x = int(round(rel_x * demo_width))
            y = int(round(rel_y * demo_height))
            if 0 <= x < demo_width and 0 <= y < demo_height:
                cv2.circle(
                    demo_frame,
                    (x, y),
                    4,
                    (0, 232, 255),
                    thickness=-1,
                    lineType=cv2.LINE_AA,
                )
                cv2.circle(
                    demo_frame,
                    (x, y),
                    7,
                    (255, 255, 255),
                    thickness=1,
                    lineType=cv2.LINE_AA,
                )

        ok, encoded = cv2.imencode(
            ".jpg",
            demo_frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.demo_stream_jpeg_quality],
        )
        if not ok:
            return

        message = CompressedImage()
        message.header.stamp = self.get_clock().now().to_msg()
        message.format = "jpeg"
        message.data = encoded.tobytes()
        self._publish_if_active(self.demo_camera_pub, message)

    def process_face_recognition(self, frame, has_face):
        if self.face_recognizer is None:
            return

        future = self.face_recognition_future
        if future is not None and future.done():
            self.face_recognition_future = None
            try:
                payload = future.result()
            except Exception as exc:
                self.get_logger().warning(f"Face recognition frame failed: {exc}")
                payload = None
            if payload is not None:
                msg = String()
                msg.data = json.dumps(payload, ensure_ascii=False)
                self._publish_if_active(self.face_recognition_pub, msg)
                self.get_logger().info(
                    "Published stable face match: "
                    f"customer_id={payload.get('customer_id')}, "
                    f"similarity={payload.get('similarity')}"
                )

        if (
            has_face
            and (
                self.face_recognition_future is None
                or self.face_recognition_future.done()
            )
        ):
            self.face_recognition_future = self.face_recognition_executor.submit(
                self.face_recognizer.process,
                frame.copy(),
            )

    def process_head_gesture(self, frame):
        if self.head_gesture_estimator is None:
            return
        gesture_frame = self.head_gesture_estimator.estimate(frame)
        if gesture_frame is not None:
            self.process_head_gesture_frame(gesture_frame)
        self.maybe_publish_pending_gesture(time.monotonic())

    def process_head_gesture_frame(self, gesture_frame: GestureFrame):
        if self.head_gesture_recognizer is None:
            return

        now = time.monotonic()
        if (
            self.tts_speaking
            or self.robot_turn_active
            or self.voice_turn_active
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

        self.queue_gesture_candidate(gesture, now)

    def queue_gesture_candidate(self, gesture: str, now: float) -> None:
        self.pending_gesture = gesture
        self.pending_gesture_deadline = now + self.gesture_candidate_hold_sec
        self.get_logger().info(
            "Head gesture candidate detected: "
            f"{gesture}; waiting {self.gesture_candidate_hold_sec:.2f}s "
            "for speech before confirming"
        )

    def maybe_publish_pending_gesture(self, now: float) -> None:
        gesture = self.pending_gesture
        if gesture not in {
            HeadGestureRecognizer.NOD,
            HeadGestureRecognizer.SHAKE,
        }:
            return

        if self.voice_turn_active:
            self.cancel_pending_gesture("voice_turn_active")
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
            f"Published confirmed user head gesture: {gesture} after voice-veto hold"
        )

    def cancel_pending_gesture(self, reason: str) -> None:
        gesture = self.pending_gesture
        if gesture in {
            HeadGestureRecognizer.NOD,
            HeadGestureRecognizer.SHAKE,
        }:
            self.get_logger().info(
                f"Discarded head gesture candidate: {gesture}, reason={reason}"
            )
        self.pending_gesture = None
        self.pending_gesture_deadline = 0.0

    def tts_status_callback(self, msg: String) -> None:
        status = str(msg.data or "").strip().lower()
        now = time.monotonic()
        if status == "speaking":
            self.tts_speaking = True
            self.voice_turn_active = False
            self.cancel_pending_gesture("robot_tts_started")
            self.reset_head_gesture_recognizer_only()
            return
        if status == "done" or status.startswith("error"):
            self.tts_speaking = False
            self.gesture_suppress_until = max(
                self.gesture_suppress_until,
                now + self.response_gesture_grace_sec,
            )
            self.cancel_pending_gesture("robot_tts_finished")
            self.reset_head_gesture_recognizer_only()

    def stt_status_callback(self, msg: String) -> None:
        status = str(msg.data or "").strip().lower()

        if status in {"speech_detected", "recording", "transcribing"}:
            if not self.voice_turn_active:
                self.get_logger().info(
                    f"Voice claimed confirmation turn: stt_status={status}"
                )
            self.voice_turn_active = True
            self.cancel_pending_gesture(f"stt_{status}")
            self.reset_head_gesture_recognizer_only()
            return

        # Keep voice ownership across STT 'done' while NLU/Decision is still
        # processing. The next robot TTS or next listen turn releases the lock.
        if status == "done" and self.voice_turn_active:
            return

        if status == "listening":
            self.voice_turn_active = False
            self.cancel_pending_gesture("new_listen_turn")
            self.reset_head_gesture_recognizer_only()
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

    def motor_command_callback(self, msg: String) -> None:
        command = str(msg.data or "").strip().upper()
        now = time.monotonic()
        if command in {"NOD", "DOUBLE_NOD", "SHAKE"}:
            self.gesture_suppress_until = max(
                self.gesture_suppress_until,
                now + self.robot_gesture_hold_sec,
            )
            self.cancel_pending_gesture("robot_head_gesture")
            self.reset_head_gesture_recognizer_only()
            return
        if command in {"TURN_LEFT", "TURN_RIGHT"}:
            self.robot_turn_active = True
            self.cancel_pending_gesture("robot_turn_started")
            self.reset_head_gesture_recognizer_only()
            return
        if command == "CENTER" and self.robot_turn_active:
            self.robot_turn_active = False
            self.gesture_suppress_until = max(
                self.gesture_suppress_until,
                now + self.robot_settle_sec,
            )
            self.cancel_pending_gesture("robot_turn_finished")
            self.reset_head_gesture_recognizer_only()

    def reset_head_gesture_recognizer_only(self):
        if self.head_gesture_recognizer is not None:
            self.head_gesture_recognizer.reset()

    def log_detection_probe(self, *, haar_faces: int, mediapipe_face: bool):
        now = time.monotonic()
        if now - self.last_detection_debug_time < 2.0:
            return
        self.last_detection_debug_time = now
        self.get_logger().info(
            "Presence probe: "
            f"haar_faces={haar_faces}, "
            f"mediapipe_face={mediapipe_face}, "
            f"face_streak={self.consecutive_face_frames}, "
            f"no_face_streak={self.consecutive_no_face_frames}, "
            f"present={self.person_detected}"
        )

    def reset_head_gesture_state(self):
        self.cancel_pending_gesture("head_gesture_state_reset")
        self.voice_turn_active = False
        if self.head_gesture_recognizer is not None:
            self.head_gesture_recognizer.reset()
        if self.head_gesture_estimator is not None:
            self.head_gesture_estimator.restart_calibration()

    def publish_presence(self, force=False, heartbeat=False):
        if not force and self.last_published_presence == self.person_detected:
            return

        changed = self.last_published_presence != self.person_detected
        person_msg = Bool()
        person_msg.data = self.person_detected
        if not self._publish_if_active(self.person_pub, person_msg):
            return
        self.last_published_presence = self.person_detected
        self.last_presence_publish_time = time.monotonic()

        if changed or not heartbeat:
            self.get_logger().info(f"Human presence changed: {self.person_detected}")

    def filter_valid_faces(self, faces, frame_width, frame_height):
        valid_faces = []
        frame_area = frame_width * frame_height

        for (x, y, w, h) in faces:
            face_area_ratio = (w * h) / frame_area
            aspect_ratio = w / h if h > 0 else 0.0

            if w < self.min_face_width or h < self.min_face_height:
                continue
            if face_area_ratio > self.max_face_area_ratio:
                continue
            if aspect_ratio < 0.65 or aspect_ratio > 1.45:
                continue

            valid_faces.append((x, y, w, h))

        return valid_faces

    def update_person_state(self, has_valid_face):
        previous = self.person_detected

        if has_valid_face:
            self.consecutive_face_frames += 1
            self.consecutive_no_face_frames = 0
        else:
            self.consecutive_no_face_frames += 1
            self.consecutive_face_frames = 0

        enough_face_frames = (
            self.consecutive_face_frames >= self.required_face_frames
        )
        enough_no_face_frames = (
            self.consecutive_no_face_frames >= self.required_no_face_frames
        )
        if not self.person_detected and enough_face_frames:
            self.person_detected = True
        elif self.person_detected and enough_no_face_frames:
            self.person_detected = False

        return previous != self.person_detected

    def destroy_node(self):
        if self.head_gesture_estimator is not None:
            self.head_gesture_estimator.close()
        self.face_recognition_executor.shutdown(wait=False, cancel_futures=True)
        if self.cap is not None:
            self.cap.release()
        super().destroy_node()


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


class _HandQuantityVisionMixin:
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


class VisionNode(_HandQuantityVisionMixin, _CoreVisionNode):
    """Production vision node with tuned head gestures and hand quantity recognition."""


def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
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
