from robot_controller.head_gesture_recognizer import HeadGestureRecognizer


def feed(samples):
    recognizer = HeadGestureRecognizer()
    result = HeadGestureRecognizer.NONE
    for timestamp, pitch, yaw, nose_x, nose_y in samples:
        detected = recognizer.add_sample(
            timestamp,
            pitch,
            yaw,
            nose_rel_x=nose_x,
            nose_rel_y=nose_y,
        )
        if detected != HeadGestureRecognizer.NONE:
            result = detected
    return result


def test_landmark_nod_uses_vertical_peak_and_return():
    assert feed(
        [
            (0.00, 0.0, 0.0, 0.000, 0.000),
            (0.10, 1.0, 2.0, 0.005, 0.018),
            (0.20, 3.0, 4.0, 0.008, 0.055),
            (0.30, 1.5, 3.0, 0.004, 0.020),
        ]
    ) == HeadGestureRecognizer.NOD


def test_nod_does_not_require_large_solvepnp_pitch_motion():
    # Physical webcam tests showed that nose landmarks move reliably even when
    # solvePnP pitch barely changes. This locks in the earlier sensitive NOD rule.
    assert feed(
        [
            (0.00, 0.1, 0.0, 0.000, 0.000),
            (0.10, 0.2, 0.5, 0.004, 0.018),
            (0.20, 0.3, 0.8, 0.006, 0.055),
            (0.30, 0.2, 0.4, 0.003, 0.018),
        ]
    ) == HeadGestureRecognizer.NOD


def test_landmark_shake_requires_both_sides_and_center_return():
    assert feed(
        [
            (0.00, 0.0, 0.0, 0.000, 0.000),
            (0.10, 1.0, -10.0, -0.050, 0.004),
            (0.20, 1.0, -2.0, -0.010, 0.006),
            (0.30, 1.0, 10.0, 0.060, 0.005),
            (0.40, 1.0, 2.0, 0.010, 0.004),
            (0.50, 1.0, -9.0, -0.050, 0.005),
            (0.60, 0.5, 0.0, 0.000, 0.004),
        ]
    ) == HeadGestureRecognizer.SHAKE


def test_landmark_still_returns_none():
    assert feed(
        [
            (0.00, 0.0, 0.0, 0.000, 0.000),
            (0.10, 0.5, 0.5, 0.005, 0.006),
            (0.20, -0.5, -0.5, -0.004, -0.005),
            (0.30, 0.2, 0.4, 0.003, 0.004),
        ]
    ) == HeadGestureRecognizer.NONE


def test_vertical_nod_is_not_reclassified_as_shake():
    assert feed(
        [
            (0.00, 0.0, 0.0, 0.000, 0.000),
            (0.10, 3.0, -6.0, -0.010, 0.020),
            (0.20, 8.0, 8.0, 0.012, 0.065),
            (0.30, 4.0, -5.0, -0.008, 0.018),
        ]
    ) == HeadGestureRecognizer.NOD
