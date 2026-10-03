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


class VisionNode(Node):
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
