from robot_controller.arm_motion import (
    HOME,
    POSES,
    ArmMotionConfig,
    ArmMotionController,
    normalize_arm_action,
)


FAST_CONFIG = ArmMotionConfig(
    pose_steps=3,
    pose_step_delay=0.0,
    home_steps=4,
    home_step_delay=0.0,
    pose_hold_seconds=0.0,
    wave_dwell_seconds=0.0,
)


def run(action):
    history = []
    controller = ArmMotionController(
        lambda angles: history.append(dict(angles)),
        sleep=lambda _seconds: None,
        config=FAST_CONFIG,
    )
    assert controller.run_action(action) is True
    return controller, history


def test_runtime_actions_map_to_confirmed_physical_poses():
    assert normalize_arm_action("POINT_RIGHT") == "POINT_RIGHT"
    assert normalize_arm_action("point_left") == "POINT_LEFT"
    assert normalize_arm_action("UNSURE") == "UNSURE"
    assert normalize_arm_action("GOODBYE_WAVE") == "GOODBYE_WAVE"
    assert normalize_arm_action("WAIT") is None


def test_every_non_wave_gesture_returns_to_home():
    for action, pose_name in (
        ("POINT_RIGHT", "right"),
        ("POINT_LEFT", "left"),
        ("UNSURE", "unsure"),
    ):
        controller, history = run(action)
        assert history[FAST_CONFIG.pose_steps - 1] == POSES[pose_name]
        assert history[-1] == HOME
        assert controller.current == HOME


def test_goodbye_wave_runs_three_cycles_then_returns_home():
    controller, history = run("GOODBYE_WAVE")
    wave_start = FAST_CONFIG.pose_steps
    wave_positions = history[wave_start:wave_start + 6]
    assert [position[8] for position in wave_positions] == [1, 105, 1, 105, 1, 105]
    assert history[-1] == HOME
    assert controller.current == HOME


def test_right_and_left_names_use_the_corrected_mappings():
    assert POSES["right"] == {
        4: 179.0, 5: 1.0, 6: 90.0, 7: 179.0,
        8: 179.0, 9: 140.0, 10: 179.0,
    }
    assert POSES["left"] == {
        4: 90.0, 5: 90.0, 6: 90.0, 7: 179.0,
        8: 1.0, 9: 140.0, 10: 179.0,
    }
