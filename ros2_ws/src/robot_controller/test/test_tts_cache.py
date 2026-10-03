from pathlib import Path

import robot_controller.tts_node as tts_module
from robot_controller.tts_node import (
    TTSNode,
    build_tts_cache_key,
    cached_audio_is_usable,
)


def test_tts_cache_key_is_stable_and_voice_profile_sensitive():
    arguments = {
        "voice": "ko-KR-SunHiNeural",
        "rate": "+5%",
        "volume": "+0%",
        "pitch": "+3Hz",
    }

    first = build_tts_cache_key("아메리카노는 몇 잔 주문하시겠어요?", **arguments)
    second = build_tts_cache_key("아메리카노는 몇 잔 주문하시겠어요?", **arguments)
    different_text = build_tts_cache_key("다시 말씀해 주세요.", **arguments)
    different_rate = build_tts_cache_key(
        "아메리카노는 몇 잔 주문하시겠어요?",
        **{**arguments, "rate": "+15%"},
    )

    assert first == second
    assert first != different_text
    assert first != different_rate


def test_tts_cache_rejects_missing_and_interrupted_wav(tmp_path: Path):
    missing = tmp_path / "missing.wav"
    interrupted = tmp_path / "interrupted.wav"
    complete = tmp_path / "complete.wav"

    interrupted.write_bytes(b"RIFF")
    complete.write_bytes(b"RIFF" + (b"audio" * 20))

    assert cached_audio_is_usable(missing) is False
    assert cached_audio_is_usable(interrupted) is False
    assert cached_audio_is_usable(complete) is True


def test_speak_synthesizes_once_then_reuses_persistent_wav(monkeypatch, tmp_path):
    calls = {"synthesis": 0, "playback": 0}

    class Logger:
        def info(self, _message):
            return None

    class FakeCommunicate:
        def __init__(self, *_args, **_kwargs):
            calls["synthesis"] += 1

        def save_sync(self, path):
            Path(path).write_bytes(b"mp3")

    class DummyNode:
        cache_enabled = True
        cache_dir = tmp_path
        voice = "ko-KR-SunHiNeural"
        rate = "+5%"
        volume = "+0%"
        pitch = "+3Hz"
        audio_player = "/usr/bin/aplay"
        alsa_device = "plughw:0,0"
        _shutdown_requested = False

        def get_logger(self):
            return Logger()

        def cache_path_for_text(self, text):
            return TTSNode.cache_path_for_text(self, text)

        def build_play_command(self, *args, **kwargs):
            return TTSNode.build_play_command(*args, **kwargs)

    def fake_run(command, **_kwargs):
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"RIFF" + (b"audio" * 20))
        else:
            calls["playback"] += 1

    monkeypatch.setattr(tts_module.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(tts_module.subprocess, "run", fake_run)

    node = DummyNode()
    TTSNode.speak(node, "아메리카노는 몇 잔 주문하시겠어요?")
    TTSNode.speak(node, "아메리카노는 몇 잔 주문하시겠어요?")

    assert calls == {"synthesis": 1, "playback": 2}
    assert len(list(tmp_path.glob("*.wav"))) == 1
