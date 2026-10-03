from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
LAUNCHER = REPO_ROOT / "scripts" / "run_ros_voice_nodes.sh"


def launcher_text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_runtime_uses_unbiased_safe_stt_module():
    text = launcher_text()

    assert "-m robot_controller.stt_node_unbiased --ros-args" in text
    assert "-m robot_controller.stt_node --ros-args" not in text
    assert 'echo "STT runtime: robot_controller.stt_node_unbiased"' in text


def test_runtime_uses_latest_additional_order_decision_module():
    text = launcher_text()

    assert "-m robot_controller.decision_node_additional_order" in text
    assert "-m robot_controller.decision_node_order_handoff" not in text
    assert (
        'echo "Decision runtime: robot_controller.decision_node_additional_order"'
        in text
    )
