from pathlib import Path

from robot_controller.stt_node_unbiased import UnbiasedSTTNode


REPO_ROOT = Path(__file__).resolve().parents[4]
LOG_LAUNCHER = REPO_ROOT / "scripts" / "run_robot_interaction_logs.sh"


def test_physical_launcher_uses_more_sensitive_normal_vad_profile():
    text = LOG_LAUNCHER.read_text(encoding="utf-8")

    assert 'PUMPKIN_STT_SPEECH_THRESHOLD:-2800.0' in text
    assert 'PUMPKIN_STT_SPEECH_START_BLOCKS:-4' in text
    assert 'PUMPKIN_STT_END_THRESHOLD:-1800.0' in text
    assert 'PUMPKIN_STT_SILENCE_DURATION:-0.6' in text


def test_physical_launcher_uses_short_confirmation_vad_profile():
    text = LOG_LAUNCHER.read_text(encoding="utf-8")

    assert 'PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS:-2' in text


def test_confirmation_start_blocks_can_be_overridden(monkeypatch):
    monkeypatch.setenv(
        UnbiasedSTTNode.CONFIRMATION_START_BLOCKS_ENV,
        "3",
    )

    assert UnbiasedSTTNode._configured_confirmation_start_blocks(4) == 3


def test_invalid_confirmation_start_blocks_fall_back(monkeypatch):
    monkeypatch.setenv(
        UnbiasedSTTNode.CONFIRMATION_START_BLOCKS_ENV,
        "not-a-number",
    )

    assert UnbiasedSTTNode._configured_confirmation_start_blocks(4) == 4
