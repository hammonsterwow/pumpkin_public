from robot_controller.head_gesture_recognizer import HeadGestureRecognizer


def feed_landmarks(samples):
    recognizer = HeadGestureRecognizer()
    result = HeadGestureRecognizer.NONE
    for timestamp, yaw, nose_x, nose_y in samples:
        detected = recognizer.add_sample(
            timestamp=timestamp,
            pitch=0.0,
            yaw=yaw,
            nose_rel_x=nose_x,
            nose_rel_y=nose_y,
        )
        if detected != HeadGestureRecognizer.NONE:
            result = detected
    return result


def test_single_turn_left_and_hold_is_not_shake():
    result = feed_landmarks(
        [
            (0.00, 0.0, 0.000, 0.000),
            (0.08, 3.0, 0.004, 0.001),
            (0.16, 10.0, 0.030, 0.001),
            (0.24, 18.0, 0.075, 0.002),
            (0.32, 25.0, 0.115, 0.002),
            (0.40, 25.0, 0.118, 0.001),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_single_turn_right_and_hold_is_not_shake():
    result = feed_landmarks(
        [
            (0.00, 0.0, 0.000, 0.000),
            (0.08, -3.0, -0.004, 0.001),
            (0.16, -10.0, -0.030, 0.001),
            (0.24, -18.0, -0.075, 0.002),
            (0.32, -25.0, -0.115, 0.002),
            (0.40, -25.0, -0.118, 0.001),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_return_from_left_to_center_is_not_shake():
    result = feed_landmarks(
        [
            (0.00, 24.0, 0.120, 0.002),
            (0.08, 20.0, 0.105, 0.002),
            (0.16, 15.0, 0.080, 0.001),
            (0.24, 10.0, 0.050, 0.001),
            (0.32, 4.0, 0.020, 0.001),
            (0.40, 0.0, 0.002, 0.001),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_return_from_right_to_center_is_not_shake():
    result = feed_landmarks(
        [
            (0.00, -24.0, -0.120, 0.002),
            (0.08, -20.0, -0.105, 0.002),
            (0.16, -15.0, -0.080, 0.001),
            (0.24, -10.0, -0.050, 0.001),
            (0.32, -4.0, -0.020, 0.001),
            (0.40, 0.0, -0.002, 0.001),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_side_pose_jitter_is_not_shake():
    result = feed_landmarks(
        [
            (0.00, 25.0, 0.220, 0.010),
            (0.08, 24.0, 0.205, 0.012),
            (0.16, 26.0, 0.235, 0.009),
            (0.24, 25.0, 0.215, 0.011),
            (0.32, 25.5, 0.228, 0.010),
            (0.40, 25.0, 0.218, 0.012),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_one_left_right_swing_without_return_is_not_enough_for_shake():
    result = feed_landmarks(
        [
            (0.00, 0.0, 0.000, 0.000),
            (0.10, -8.0, -0.030, 0.001),
            (0.20, -18.0, -0.080, 0.002),
            (0.30, -5.0, -0.020, 0.001),
            (0.40, 10.0, 0.040, 0.001),
            (0.50, 18.0, 0.085, 0.002),
        ]
    )
    assert result == HeadGestureRecognizer.NONE


def test_two_horizontal_swings_and_center_return_are_detected_as_shake():
    result = feed_landmarks(
        [
            (0.00, 0.0, 0.000, 0.000),
            (0.10, -8.0, -0.035, 0.001),
            (0.20, -18.0, -0.085, 0.002),
            (0.30, -4.0, -0.020, 0.001),
            (0.40, 10.0, 0.050, 0.001),
            (0.50, 18.0, 0.090, 0.002),
            (0.60, 4.0, 0.020, 0.001),
            (0.70, -12.0, -0.055, 0.001),
            (0.80, -18.0, -0.090, 0.002),
            (0.84, 0.0, 0.000, 0.001),
        ]
    )
    assert result == HeadGestureRecognizer.SHAKE
