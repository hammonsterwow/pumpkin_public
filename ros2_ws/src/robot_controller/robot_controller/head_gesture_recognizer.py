from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median
from typing import Deque, Optional


@dataclass(frozen=True)
class HeadPoseSample:
    timestamp: float
    pitch: float
    yaw: float
    nod_feature: Optional[float] = None
    nose_rel_x: Optional[float] = None
    nose_rel_y: Optional[float] = None


@dataclass
class HeadGestureConfig:
    history_seconds: float = 1.5
    cooldown_seconds: float = 0.8
    max_lock_seconds: float = 1.6
    sample_gap_reset_seconds: float = 0.30

    # Landmark rules selected from the collected p01/p02/p03 sliding-window data.
    landmark_window_seconds: float = 0.40
    shake_landmark_window_seconds: float = 0.85
    nod_landmark_range: float = 0.040
    nod_landmark_return: float = 0.012
    nod_landmark_dominance: float = 1.15
    shake_landmark_range: float = 0.045
    shake_landmark_dominance: float = 1.45
    shake_landmark_center_margin: float = 0.010
    shake_landmark_direction_epsilon: float = 0.006
    shake_landmark_min_reversals: int = 2
    shake_landmark_return_margin: float = 0.025
    shake_pose_excursion_deg: float = 7.0
    shake_pose_return_tolerance_deg: float = 8.0
    landmark_min_samples: int = 4

    # Legacy pose fallback for callers that do not supply landmark features.
    nod_threshold_deg: float = 1.8
    nod_min_return_deg: float = 0.7
    nod_max_yaw_range_deg: float = 18.0
    nod_window_seconds: float = 0.75
    nod_min_pitch_dominance_ratio: float = 0.85
    shake_threshold_deg: float = 6.0
    shake_max_pitch_range_deg: float = 16.0
    shake_min_range_dominance_ratio: float = 1.35
    shake_min_motion_dominance_ratio: float = 1.25

    min_gesture_duration_seconds: float = 0.08
    max_gesture_duration_seconds: float = 1.40
    min_peak_velocity_deg_per_sec: float = 5.0
    neutral_pitch_tolerance_deg: float = 9.0
    neutral_yaw_tolerance_deg: float = 12.0
    rearm_stable_seconds: float = 0.15

    # Backward-compatible fields retained for existing configs/tests.
    nod_feature_threshold: float = 0.75
    nod_feature_min_return: float = 0.30
    nod_feature_return_fraction: float = 0.82
    shake_axis_dominance_ratio: float = 1.05
    shake_cross_axis_ratio: float = 0.80


class HeadGestureRecognizer:
    """Classify one physical head movement as NOD, SHAKE or NONE.

    NOD intentionally uses the earlier landmark-only rule because physical tests
    showed that requiring extra pose/center constraints made ordinary customer
    nods too easy to miss. SHAKE stays conservative: it must move across both
    sides and return toward the calibrated center so a simple side glance is not
    interpreted as a negative answer.
    """

    NONE = "NONE"
    NOD = "NOD"
    SHAKE = "SHAKE"

    def __init__(self, config: Optional[HeadGestureConfig] = None) -> None:
        self.config = config or HeadGestureConfig()
        self._validate_config()
        self._samples: Deque[HeadPoseSample] = deque()
        self._last_gesture_time = float("-inf")
        self._armed = True
        self._neutral_since: Optional[float] = None

    @property
    def is_armed(self) -> bool:
        return self._armed

    def reset(self) -> None:
        self._samples.clear()
        self._last_gesture_time = float("-inf")
        self._armed = True
        self._neutral_since = None

    def add_sample(
        self,
        timestamp: float,
        pitch: float,
        yaw: float,
        nod_feature: Optional[float] = None,
        nose_rel_x: Optional[float] = None,
        nose_rel_y: Optional[float] = None,
    ) -> str:
        sample = HeadPoseSample(
            timestamp=float(timestamp),
            pitch=float(pitch),
            yaw=float(yaw),
            nod_feature=None if nod_feature is None else float(nod_feature),
            nose_rel_x=None if nose_rel_x is None else float(nose_rel_x),
            nose_rel_y=None if nose_rel_y is None else float(nose_rel_y),
        )

        if not self._armed:
            self._update_rearm_state(sample)
            return self.NONE

        if (
            self._samples
            and sample.timestamp - self._samples[-1].timestamp
            > self.config.sample_gap_reset_seconds
        ):
            self._samples.clear()

        self._samples.append(sample)
        self._trim_history(sample.timestamp)
        gesture = self._detect_gesture()
        if gesture != self.NONE:
            self._last_gesture_time = sample.timestamp
            self._samples.clear()
            self._armed = False
            self._neutral_since = None
        return gesture

    def _validate_config(self) -> None:
        if self.config.history_seconds <= 0.0:
            raise ValueError("history_seconds must be positive.")
        if self.config.landmark_window_seconds <= 0.0:
            raise ValueError("landmark_window_seconds must be positive.")
        if self.config.shake_landmark_window_seconds <= 0.0:
            raise ValueError("shake_landmark_window_seconds must be positive.")
        if self.config.landmark_min_samples < 3:
            raise ValueError("landmark_min_samples must be at least 3.")
        if self.config.shake_landmark_center_margin < 0.0:
            raise ValueError("shake_landmark_center_margin must be non-negative.")
        if self.config.shake_landmark_direction_epsilon < 0.0:
            raise ValueError("shake_landmark_direction_epsilon must be non-negative.")
        if self.config.shake_landmark_min_reversals < 1:
            raise ValueError("shake_landmark_min_reversals must be at least 1.")
        if self.config.shake_landmark_return_margin < 0.0:
            raise ValueError("shake_landmark_return_margin must be non-negative.")
        if self.config.max_lock_seconds < self.config.cooldown_seconds:
            raise ValueError("max_lock_seconds must be >= cooldown_seconds.")

    def _update_rearm_state(self, sample: HeadPoseSample) -> None:
        elapsed = sample.timestamp - self._last_gesture_time
        if elapsed < self.config.cooldown_seconds:
            self._neutral_since = None
            return
        if elapsed >= self.config.max_lock_seconds:
            self._armed = True
            self._neutral_since = None
            self._samples.clear()
            return
        if not self._is_neutral(sample):
            self._neutral_since = None
            return
        if self._neutral_since is None:
            self._neutral_since = sample.timestamp
            return
        if sample.timestamp - self._neutral_since >= self.config.rearm_stable_seconds:
            self._armed = True
            self._neutral_since = None
            self._samples.clear()

    def _is_neutral(self, sample: HeadPoseSample) -> bool:
        pose_neutral = (
            abs(sample.pitch) <= self.config.neutral_pitch_tolerance_deg
            and abs(sample.yaw) <= self.config.neutral_yaw_tolerance_deg
        )
        if sample.nose_rel_x is None or sample.nose_rel_y is None:
            return pose_neutral
        return (
            pose_neutral
            and abs(sample.nose_rel_x) <= 0.05
            and abs(sample.nose_rel_y) <= 0.05
        )

    def _trim_history(self, now: float) -> None:
        cutoff = now - self.config.history_seconds
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

    def _detect_gesture(self) -> str:
        if len(self._samples) < 3:
            return self.NONE
        samples = list(self._samples)
        landmark_samples = [
            sample
            for sample in samples
            if sample.nose_rel_x is not None and sample.nose_rel_y is not None
        ]
        if len(landmark_samples) >= self.config.landmark_min_samples:
            return self._detect_landmark_gesture(landmark_samples)
        return self._detect_pose_fallback(samples)

    def _detect_landmark_gesture(self, samples: list[HeadPoseSample]) -> str:
        latest = samples[-1].timestamp

        shake_cutoff = latest - self.config.shake_landmark_window_seconds
        shake_window = [sample for sample in samples if sample.timestamp >= shake_cutoff]
        if len(shake_window) >= self.config.landmark_min_samples:
            xs = [float(sample.nose_rel_x) for sample in shake_window]
            ys = [float(sample.nose_rel_y) for sample in shake_window]
            yaws = [float(sample.yaw) for sample in shake_window]
            x_range = max(xs) - min(xs)
            y_range = max(ys) - min(ys)
            x_motion = self._value_motion(xs)
            y_motion = self._value_motion(ys)

            center_margin = self.config.shake_landmark_center_margin
            crosses_face_center = (
                min(xs) <= -center_margin and max(xs) >= center_margin
            )
            reversals = self._count_direction_reversals(
                xs,
                self.config.shake_landmark_direction_epsilon,
            )
            pose_crosses_both_sides = (
                min(yaws) <= -self.config.shake_pose_excursion_deg
                and max(yaws) >= self.config.shake_pose_excursion_deg
            )
            returns_to_center = (
                abs(xs[-1]) <= self.config.shake_landmark_return_margin
                and abs(yaws[-1]) <= self.config.shake_pose_return_tolerance_deg
            )

            if (
                x_range >= self.config.shake_landmark_range
                and x_range >= y_range * self.config.shake_landmark_dominance
                and x_motion >= y_motion * 1.20
                and crosses_face_center
                and reversals >= self.config.shake_landmark_min_reversals
                and pose_crosses_both_sides
                and returns_to_center
            ):
                return self.SHAKE

        # Restore the earlier NOD detector. It deliberately does not require an
        # additional solvePnP pitch excursion or exact neutral-center finish.
        nod_cutoff = latest - self.config.landmark_window_seconds
        nod_window = [sample for sample in samples if sample.timestamp >= nod_cutoff]
        if len(nod_window) < self.config.landmark_min_samples:
            return self.NONE

        xs = [float(sample.nose_rel_x) for sample in nod_window]
        ys = [float(sample.nose_rel_y) for sample in nod_window]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)

        if (
            y_range >= self.config.nod_landmark_range
            and y_range >= x_range * self.config.nod_landmark_dominance
            and self._has_peak_and_return(ys, self.config.nod_landmark_return)
        ):
            return self.NOD
        return self.NONE

    def _detect_pose_fallback(self, samples: list[HeadPoseSample]) -> str:
        cutoff = samples[-1].timestamp - self.config.max_gesture_duration_seconds
        samples = [sample for sample in samples if sample.timestamp >= cutoff]
        if len(samples) < 3:
            return self.NONE
        duration = samples[-1].timestamp - samples[0].timestamp
        if duration < self.config.min_gesture_duration_seconds:
            return self.NONE
        if self._is_pose_nod(samples):
            return self.NOD
        if self._is_pose_shake(samples):
            return self.SHAKE
        return self.NONE

    def _is_pose_nod(self, samples: list[HeadPoseSample]) -> bool:
        latest = samples[-1].timestamp
        recent = [
            sample
            for sample in samples
            if sample.timestamp >= latest - self.config.nod_window_seconds
        ]
        if len(recent) < 4:
            return False
        pitches = [sample.pitch for sample in recent]
        yaws = [sample.yaw for sample in recent]
        if max(yaws) - min(yaws) > self.config.nod_max_yaw_range_deg:
            return False
        if (
            self._value_motion(pitches)
            < self._value_motion(yaws) * self.config.nod_min_pitch_dominance_ratio
        ):
            return False
        if max(pitches) - min(pitches) < self.config.nod_threshold_deg:
            return False
        return self._has_peak_and_return(pitches, self.config.nod_min_return_deg)

    def _is_pose_shake(self, samples: list[HeadPoseSample]) -> bool:
        pitches = [sample.pitch for sample in samples]
        yaws = [sample.yaw for sample in samples]
        pitch_range = max(pitches) - min(pitches)
        yaw_range = max(yaws) - min(yaws)
        if pitch_range > self.config.shake_max_pitch_range_deg:
            return False
        if yaw_range < pitch_range * self.config.shake_min_range_dominance_ratio:
            return False
        if (
            self._value_motion(yaws)
            < self._value_motion(pitches)
            * self.config.shake_min_motion_dominance_ratio
        ):
            return False
        return (
            min(yaws) <= -self.config.shake_threshold_deg
            and max(yaws) >= self.config.shake_threshold_deg
        )

    @staticmethod
    def _value_motion(values: list[float]) -> float:
        return sum(
            abs(current - previous)
            for previous, current in zip(values, values[1:])
        )

    @staticmethod
    def _count_direction_reversals(values: list[float], epsilon: float) -> int:
        directions: list[int] = []
        for previous, current in zip(values, values[1:]):
            delta = current - previous
            if abs(delta) < epsilon:
                continue
            direction = 1 if delta > 0.0 else -1
            if not directions or direction != directions[-1]:
                directions.append(direction)
        return max(0, len(directions) - 1)

    @staticmethod
    def _has_peak_and_return(values: list[float], minimum_return: float) -> bool:
        if len(values) < 4:
            return False
        baseline = float(median(values[: min(3, len(values) - 1)]))
        peak_index = max(
            range(len(values)),
            key=lambda index: abs(values[index] - baseline),
        )
        if peak_index == 0 or peak_index >= len(values) - 1:
            return False
        peak_delta = abs(values[peak_index] - baseline)
        returned = abs(values[peak_index] - values[-1])
        return (
            returned >= minimum_return
            and abs(values[-1] - baseline) < peak_delta
        )
