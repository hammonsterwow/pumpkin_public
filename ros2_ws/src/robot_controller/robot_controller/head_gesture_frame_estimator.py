from __future__ import annotations

import time
from dataclasses import dataclass
from statistics import median
from typing import Optional

import cv2
import numpy as np


@dataclass(frozen=True)
class GestureFrame:
    pitch: float
    yaw: float
    roll: float
    nose_rel_x: float
    nose_rel_y: float


class HeadGestureFrameEstimator:
    """Estimate pose and normalized landmark features with one FaceMesh pass."""

    CALIBRATING = "CALIBRATING"
    READY = "READY"
    FACE_NOT_DETECTED = "FACE_NOT_DETECTED"

    _POSE_IDS = (1, 152, 33, 263, 61, 291)

    def __init__(
        self,
        calibration_duration_sec: float = 0.45,
        calibration_min_samples: int = 6,
        smooth_alpha: float = 0.45,
    ) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "MediaPipe is not installed. Run: "
                "python -m pip install mediapipe==0.10.18"
            ) from exc

        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._calibration_duration_sec = calibration_duration_sec
        self._calibration_min_samples = calibration_min_samples
        self._smooth_alpha = smooth_alpha

        self._calibration_started_at: Optional[float] = None
        self._calibration_samples: list[tuple[float, float, float, float, float]] = []
        self._neutral: Optional[tuple[float, float, float, float, float]] = None
        self._smoothed: Optional[np.ndarray] = None
        self._face_detected = False
        self._display_landmarks: tuple[tuple[float, float], ...] = ()

    @property
    def status(self) -> str:
        if not self._face_detected:
            return self.FACE_NOT_DETECTED
        return self.READY if self._neutral is not None else self.CALIBRATING

    @property
    def is_calibrated(self) -> bool:
        return self._neutral is not None

    @property
    def calibration_progress(self) -> float:
        if self._neutral is not None:
            return 1.0
        if self._calibration_started_at is None:
            return 0.0
        elapsed = time.monotonic() - self._calibration_started_at
        time_progress = min(1.0, elapsed / self._calibration_duration_sec)
        sample_progress = min(
            1.0,
            len(self._calibration_samples) / float(self._calibration_min_samples),
        )
        return min(time_progress, sample_progress)

    @property
    def display_landmarks(self) -> tuple[tuple[float, float], ...]:
        """Return the six FaceMesh points already used for head-pose estimation.

        Coordinates are normalized to the current camera frame. The demo stream
        uses these points only for drawing; no second MediaPipe inference pass is
        required.
        """

        return self._display_landmarks

    @staticmethod
    def _angle_delta(angle: float, reference: float) -> float:
        return (angle - reference + 180.0) % 360.0 - 180.0

    def estimate(self, frame_bgr: np.ndarray) -> Optional[GestureFrame]:
        if frame_bgr is None or frame_bgr.size == 0:
            self._display_landmarks = ()
            return None

        result = self._face_mesh.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        if not result.multi_face_landmarks:
            self._face_detected = False
            self._display_landmarks = ()
            return None

        self._face_detected = True
        landmarks = result.multi_face_landmarks[0].landmark
        self._display_landmarks = tuple(
            (float(landmarks[index].x), float(landmarks[index].y))
            for index in self._POSE_IDS
        )

        pose = self._solve_pose(frame_bgr, landmarks)
        if pose is None:
            return None

        nose = landmarks[1]
        chin = landmarks[152]
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        left_face = landmarks[234]
        right_face = landmarks[454]

        eye_x = (left_eye.x + right_eye.x) * 0.5
        eye_y = (left_eye.y + right_eye.y) * 0.5
        face_width = max(abs(right_face.x - left_face.x), 1e-6)
        face_height = max(abs(chin.y - eye_y), 1e-6)
        values = np.array(
            [
                pose[0],
                pose[1],
                pose[2],
                (nose.x - eye_x) / face_width,
                (nose.y - eye_y) / face_height,
            ],
            dtype=np.float64,
        )

        if self._smoothed is None:
            self._smoothed = values
        else:
            angle_deltas = np.array(
                [
                    self._angle_delta(values[0], self._smoothed[0]),
                    self._angle_delta(values[1], self._smoothed[1]),
                    self._angle_delta(values[2], self._smoothed[2]),
                ]
            )
            self._smoothed[:3] += self._smooth_alpha * angle_deltas
            self._smoothed[3:] = (
                self._smooth_alpha * values[3:]
                + (1.0 - self._smooth_alpha) * self._smoothed[3:]
            )

        now = time.monotonic()
        if self._neutral is None:
            self._update_calibration(now, self._smoothed)
            if self._neutral is None:
                return None

        neutral = self._neutral
        return GestureFrame(
            pitch=self._angle_delta(float(self._smoothed[0]), neutral[0]),
            yaw=self._angle_delta(float(self._smoothed[1]), neutral[1]),
            roll=self._angle_delta(float(self._smoothed[2]), neutral[2]),
            nose_rel_x=float(self._smoothed[3] - neutral[3]),
            nose_rel_y=float(self._smoothed[4] - neutral[4]),
        )

    def restart_calibration(self) -> None:
        self._calibration_started_at = None
        self._calibration_samples.clear()
        self._neutral = None
        self._smoothed = None
        self._display_landmarks = ()

    def close(self) -> None:
        self._face_mesh.close()

    def _update_calibration(self, now: float, values: np.ndarray) -> None:
        if self._calibration_started_at is None:
            self._calibration_started_at = now
        self._calibration_samples.append(tuple(float(value) for value in values))
        if len(self._calibration_samples) < self._calibration_min_samples:
            return
        if now - self._calibration_started_at < self._calibration_duration_sec:
            return

        recent = self._calibration_samples[-30:]
        reference = recent[0]
        columns: list[list[float]] = [[] for _ in range(5)]
        for sample in recent:
            for index in range(3):
                columns[index].append(
                    reference[index] + self._angle_delta(sample[index], reference[index])
                )
            columns[3].append(sample[3])
            columns[4].append(sample[4])

        self._neutral = tuple(float(median(column)) for column in columns)
        self._calibration_samples.clear()

    def _solve_pose(self, frame: np.ndarray, landmarks) -> Optional[tuple[float, float, float]]:
        height, width = frame.shape[:2]
        image_points = np.array(
            [(landmarks[index].x * width, landmarks[index].y * height) for index in self._POSE_IDS],
            dtype=np.float64,
        )
        model_points = np.array(
            [
                (0.0, 0.0, 0.0),
                (0.0, -63.6, -12.5),
                (-43.3, 32.7, -26.0),
                (43.3, 32.7, -26.0),
                (-28.9, -28.9, -24.1),
                (28.9, -28.9, -24.1),
            ],
            dtype=np.float64,
        )
        focal_length = float(width)
        camera_matrix = np.array(
            [
                [focal_length, 0.0, width / 2.0],
                [0.0, focal_length, height / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        success, rotation_vector, _ = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            np.zeros((4, 1), dtype=np.float64),
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            return None
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        angles, *_ = cv2.RQDecomp3x3(rotation_matrix)
        values = np.asarray(angles, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            return None
        return float(angles[0]), float(angles[1]), float(angles[2])
