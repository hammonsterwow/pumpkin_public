from __future__ import annotations

from types import SimpleNamespace

from robot_controller.hand_quantity_gesture import HandQuantityGestureRecognizer


def point(x, y):
    return SimpleNamespace(x=x, y=y)


def make_landmarks(quantity: int):
    landmarks = [point(0.5, 0.9) for _ in range(21)]

    # Folded defaults.
    landmarks[3] = point(0.36, 0.72)
    landmarks[4] = point(0.42, 0.80)
    landmarks[6] = point(0.42, 0.55)
    landmarks[8] = point(0.42, 0.72)
    landmarks[10] = point(0.52, 0.55)
    landmarks[12] = point(0.52, 0.72)
    landmarks[14] = point(0.62, 0.55)
    landmarks[16] = point(0.62, 0.72)
    landmarks[18] = point(0.72, 0.58)
    landmarks[20] = point(0.72, 0.74)

    if quantity >= 1:
        landmarks[8] = point(0.40, 0.20)
    if quantity >= 2:
        landmarks[12] = point(0.52, 0.15)
    if quantity >= 3:
        landmarks[16] = point(0.62, 0.18)
    if quantity >= 4:
        landmarks[20] = point(0.72, 0.22)
    if quantity >= 5:
        landmarks[3] = point(0.34, 0.66)
        landmarks[4] = point(0.14, 0.56)

    return landmarks


def test_one_to_five_fingers_are_classified():
    expected = {
        1: "ONE_FINGER",
        2: "TWO_FINGERS",
        3: "THREE_FINGERS",
        4: "FOUR_FINGERS",
        5: "FIVE_FINGERS",
    }
    for quantity, gesture in expected.items():
        assert (
            HandQuantityGestureRecognizer.classify_quantity_pose(
                make_landmarks(quantity)
            )
            == gesture
        )


def test_non_sequential_finger_pattern_is_rejected():
    landmarks = make_landmarks(1)
    landmarks[12] = point(0.52, 0.15)
    landmarks[8] = point(0.42, 0.72)

    assert (
        HandQuantityGestureRecognizer.classify_quantity_pose(landmarks)
        is None
    )


def test_tiny_distant_hand_is_rejected():
    landmarks = [point(0.5, 0.5) for _ in range(21)]
    landmarks[6] = point(0.50, 0.49)
    landmarks[8] = point(0.50, 0.47)

    assert (
        HandQuantityGestureRecognizer.classify_quantity_pose(landmarks)
        is None
    )


def test_temporal_gate_emits_once_until_pose_changes_or_releases():
    recognizer = HandQuantityGestureRecognizer.__new__(
        HandQuantityGestureRecognizer
    )
    recognizer.hold_sec = 0.30
    recognizer.min_frames = 3
    recognizer._candidate = None
    recognizer._candidate_started_at = 0.0
    recognizer._candidate_frames = 0
    recognizer._emitted_for_hold = False

    assert recognizer._update_candidate("THREE_FINGERS", 1.00) is None
    assert recognizer._update_candidate("THREE_FINGERS", 1.15) is None
    assert (
        recognizer._update_candidate("THREE_FINGERS", 1.31)
        == "THREE_FINGERS"
    )
    assert recognizer._update_candidate("THREE_FINGERS", 1.50) is None

    assert recognizer._update_candidate("FOUR_FINGERS", 1.60) is None
    assert recognizer._update_candidate("FOUR_FINGERS", 1.76) is None
    assert (
        recognizer._update_candidate("FOUR_FINGERS", 1.91)
        == "FOUR_FINGERS"
    )

    recognizer._update_candidate(None, 2.00)
    assert recognizer._update_candidate("ONE_FINGER", 2.10) is None
