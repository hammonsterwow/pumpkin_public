from __future__ import annotations

import math
import time
from typing import Any, Sequence

import cv2


class HandQuantityGestureRecognizer:
    """Recognize stable one-to-five finger poses for quantity input.

    Quantity poses use 1=index, 2=index+middle, 3=index+middle+ring,
    4=four non-thumb fingers, and 5=all five fingers.

    A pose must remain stable for both a minimum number of frames and a minimum
    amount of time. The recognizer emits only once per hold; the customer must
    release or change the pose before the same gesture can fire again.
    """

    ONE_FINGER = "ONE_FINGER"
    TWO_FINGERS = "TWO_FINGERS"
    THREE_FINGERS = "THREE_FINGERS"
    FOUR_FINGERS = "FOUR_FINGERS"
    FIVE_FINGERS = "FIVE_FINGERS"

    WRIST = 0
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_PIP = 6
    INDEX_TIP = 8
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_PIP = 14
    RING_TIP = 16
    LITTLE_PIP = 18
    LITTLE_TIP = 20

    def __init__(
        self,
        *,
        hold_sec: float = 0.35,
        min_frames: int = 3,
        extension_ratio: float = 1.15,
        min_hand_span: float = 0.12,
    ) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "MediaPipe is not installed. On Jetson/Python 3.10 install "
                "mediapipe==0.10.18."
            ) from exc

        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self.hold_sec = max(0.0, float(hold_sec))
        self.min_frames = max(1, int(min_frames))
        self.extension_ratio = max(1.01, float(extension_ratio))
        self.min_hand_span = max(0.0, float(min_hand_span))

        self._candidate: str | None = None
        self._candidate_started_at = 0.0
        self._candidate_frames = 0
        self._emitted_for_hold = False
        self._display_landmarks: tuple[tuple[float, float], ...] = ()

    @property
    def display_landmarks(self) -> tuple[tuple[float, float], ...]:
        return self._display_landmarks

    @staticmethod
    def _distance(a: Any, b: Any) -> float:
        return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))

    @classmethod
    def _finger_extended(
        cls,
        landmarks: Sequence[Any],
        pip_index: int,
        tip_index: int,
        *,
        extension_ratio: float,
    ) -> bool:
        wrist = landmarks[cls.WRIST]
        pip = landmarks[pip_index]
        tip = landmarks[tip_index]
        pip_distance = cls._distance(wrist, pip)
        tip_distance = cls._distance(wrist, tip)
        if pip_distance <= 1e-6:
            return False
        return tip_distance >= pip_distance * extension_ratio

    @classmethod
    def _thumb_extended(
        cls,
        landmarks: Sequence[Any],
        *,
        extension_ratio: float,
    ) -> bool:
        wrist = landmarks[cls.WRIST]
        thumb_ip = landmarks[cls.THUMB_IP]
        thumb_tip = landmarks[cls.THUMB_TIP]
        ip_distance = cls._distance(wrist, thumb_ip)
        tip_distance = cls._distance(wrist, thumb_tip)
        if ip_distance <= 1e-6:
            return False
        return tip_distance >= ip_distance * extension_ratio

    @classmethod
    def classify_quantity_pose(
        cls,
        landmarks: Sequence[Any],
        *,
        extension_ratio: float = 1.15,
        min_hand_span: float = 0.12,
    ) -> str | None:
        if len(landmarks) < 21:
            return None

        xs = [float(point.x) for point in landmarks]
        ys = [float(point.y) for point in landmarks]
        hand_span = max(max(xs) - min(xs), max(ys) - min(ys))
        if hand_span < min_hand_span:
            return None

        index_extended = cls._finger_extended(
            landmarks, cls.INDEX_PIP, cls.INDEX_TIP,
            extension_ratio=extension_ratio,
        )
        middle_extended = cls._finger_extended(
            landmarks, cls.MIDDLE_PIP, cls.MIDDLE_TIP,
            extension_ratio=extension_ratio,
        )
        ring_extended = cls._finger_extended(
            landmarks, cls.RING_PIP, cls.RING_TIP,
            extension_ratio=extension_ratio,
        )
        little_extended = cls._finger_extended(
            landmarks, cls.LITTLE_PIP, cls.LITTLE_TIP,
            extension_ratio=extension_ratio,
        )

        pattern = (
            index_extended,
            middle_extended,
            ring_extended,
            little_extended,
        )
        if pattern == (True, False, False, False):
            return cls.ONE_FINGER
        if pattern == (True, True, False, False):
            return cls.TWO_FINGERS
        if pattern == (True, True, True, False):
            return cls.THREE_FINGERS
        if pattern == (True, True, True, True):
            thumb_extended = cls._thumb_extended(
                landmarks,
                extension_ratio=max(1.08, extension_ratio - 0.05),
            )
            return cls.FIVE_FINGERS if thumb_extended else cls.FOUR_FINGERS
        return None

    @classmethod
    def is_two_finger_pose(
        cls,
        landmarks: Sequence[Any],
        *,
        extension_ratio: float = 1.15,
        min_hand_span: float = 0.12,
    ) -> bool:
        return cls.classify_quantity_pose(
            landmarks,
            extension_ratio=extension_ratio,
            min_hand_span=min_hand_span,
        ) == cls.TWO_FINGERS

    def process(self, frame_bgr, *, timestamp: float | None = None) -> str | None:
        if frame_bgr is None or frame_bgr.size == 0:
            self.reset()
            return None

        now = time.monotonic() if timestamp is None else float(timestamp)
        result = self._hands.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

        if not result.multi_hand_landmarks:
            self._display_landmarks = ()
            self._clear_candidate()
            return None

        hand = result.multi_hand_landmarks[0]
        landmarks = hand.landmark
        self._display_landmarks = tuple(
            (float(point.x), float(point.y))
            for point in landmarks
        )

        gesture = self.classify_quantity_pose(
            landmarks,
            extension_ratio=self.extension_ratio,
            min_hand_span=self.min_hand_span,
        )

        return self._update_candidate(gesture, now)

    def _update_candidate(self, gesture: str | None, now: float) -> str | None:
        if gesture is None:
            self._clear_candidate()
            return None

        if gesture != self._candidate:
            self._candidate = gesture
            self._candidate_started_at = now
            self._candidate_frames = 1
            self._emitted_for_hold = False
            return None

        self._candidate_frames += 1
        stable_long_enough = now - self._candidate_started_at >= self.hold_sec
        stable_frames = self._candidate_frames >= self.min_frames
        if stable_long_enough and stable_frames and not self._emitted_for_hold:
            self._emitted_for_hold = True
            return gesture
        return None

    def _clear_candidate(self) -> None:
        self._candidate = None
        self._candidate_started_at = 0.0
        self._candidate_frames = 0
        self._emitted_for_hold = False

    def reset(self) -> None:
        self._display_landmarks = ()
        self._clear_candidate()

    def close(self) -> None:
        self._hands.close()
