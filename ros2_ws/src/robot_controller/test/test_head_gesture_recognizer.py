from robot_controller.head_gesture_recognizer import (
    HeadGestureConfig,
    HeadGestureRecognizer,
)


def make_recognizer() -> HeadGestureRecognizer:
    return HeadGestureRecognizer(
        HeadGestureConfig(
            history_seconds=1.4,
            cooldown_seconds=0.5,
            max_lock_seconds=1.0,
            sample_gap_reset_seconds=0.30,
            nod_threshold_deg=3.0,
            nod_min_return_deg=1.3,
            nod_max_yaw_range_deg=9.0,
            shake_threshold_deg=5.0,
            shake_max_pitch_range_deg=14.0,
            shake_cross_axis_ratio=0.80,
            min_gesture_duration_seconds=0.1,
            max_gesture_duration_seconds=1.2,
            min_peak_velocity_deg_per_sec=7.0,
            neutral_pitch_tolerance_deg=7.0,
            neutral_yaw_tolerance_deg=9.0,
            rearm_stable_seconds=0.2,
        )
    )


def feed(recognizer, samples):
    result = HeadGestureRecognizer.NONE
    for timestamp, pitch, yaw in samples:
        detected = recognizer.add_sample(timestamp, pitch, yaw)
        if detected != HeadGestureRecognizer.NONE:
            result = detected
    return result


def test_detects_nod():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 3.0, 0.5),
            (0.4, 7.0, 1.0),
            (0.6, 4.0, 0.5),
            (0.8, 1.5, 0.0),
        ],
    )
    assert result == HeadGestureRecognizer.NOD
    assert recognizer.is_armed is False


def test_detects_small_webcam_like_nod():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.15, 1.0, 0.2),
            (0.30, 4.0, 0.5),
            (0.45, 2.0, 0.1),
        ],
    )
    assert result == HeadGestureRecognizer.NOD


def test_nod_does_not_need_exact_zero_return():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 1.0, 0.0),
            (0.2, 3.5, 0.5),
            (0.4, 7.0, 1.0),
            (0.6, 5.0, 0.5),
            (0.8, 3.0, 0.0),
        ],
    )
    assert result == HeadGestureRecognizer.NOD


def test_detects_natural_small_shake():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.15, 0.5, -6.0),
            (0.30, 0.8, 0.0),
            (0.45, 0.5, 6.5),
        ],
    )
    assert result == HeadGestureRecognizer.SHAKE


def test_detects_larger_shake():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 1.0, -12.0),
            (0.4, 1.5, 0.0),
            (0.6, 1.0, 13.0),
        ],
    )
    assert result == HeadGestureRecognizer.SHAKE
    assert recognizer.is_armed is False


def test_static_pose_returns_none():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.7, 0.5),
            (0.4, -0.8, -0.5),
            (0.6, 0.5, 0.8),
        ],
    )
    assert result == HeadGestureRecognizer.NONE


def test_ambiguous_diagonal_motion_returns_none():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 15.0, -11.0),
            (0.4, -2.0, 11.0),
        ],
    )
    assert result == HeadGestureRecognizer.NONE


def test_horizontal_motion_is_not_nod():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 4.0, -8.0),
            (0.4, -3.0, 8.0),
            (0.6, 1.0, 0.0),
        ],
    )
    assert result != HeadGestureRecognizer.NOD


def test_slow_look_is_not_a_shake():
    recognizer = make_recognizer()
    result = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.8, 0.5, -6.0),
            (1.6, 0.5, 6.0),
        ],
    )
    assert result == HeadGestureRecognizer.NONE


def test_one_shake_emits_only_once_during_cooldown():
    recognizer = make_recognizer()
    first = feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.5, -6.0),
            (0.4, 0.5, 6.0),
        ],
    )
    assert first == HeadGestureRecognizer.SHAKE

    repeated_tail = feed(
        recognizer,
        [
            (0.6, 0.0, -6.0),
            (0.8, 0.0, 6.0),
        ],
    )
    assert repeated_tail == HeadGestureRecognizer.NONE
    assert recognizer.is_armed is False


def test_rearms_after_neutral_return():
    recognizer = make_recognizer()
    feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.5, -6.0),
            (0.4, 0.5, 6.0),
        ],
    )
    feed(
        recognizer,
        [
            (0.9, 0.0, 0.0),
            (1.1, 0.0, 0.0),
            (1.3, 0.0, 0.0),
        ],
    )
    assert recognizer.is_armed is True


def test_rearms_after_timeout_even_when_neutral_is_offset():
    recognizer = make_recognizer()
    feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.5, -6.0),
            (0.4, 0.5, 6.0),
        ],
    )
    feed(
        recognizer,
        [
            (0.8, 8.0, 10.0),
            (1.2, 8.0, 10.0),
            (1.5, 8.0, 10.0),
        ],
    )
    assert recognizer.is_armed is True


def test_second_gesture_is_allowed_after_rearm():
    recognizer = make_recognizer()
    feed(
        recognizer,
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.5, -6.0),
            (0.4, 0.5, 6.0),
        ],
    )
    feed(
        recognizer,
        [
            (0.9, 0.0, 0.0),
            (1.1, 0.0, 0.0),
            (1.3, 0.0, 0.0),
        ],
    )

    second = feed(
        recognizer,
        [
            (1.5, 0.0, 0.0),
            (1.65, 1.0, 0.2),
            (1.80, 4.0, 0.5),
            (1.95, 2.0, 0.0),
        ],
    )
    assert second == HeadGestureRecognizer.NOD
