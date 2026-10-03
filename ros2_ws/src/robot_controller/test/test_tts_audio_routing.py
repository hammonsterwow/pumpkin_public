from robot_controller.tts_node import TTSNode


def test_explicit_respeaker_output_is_preserved_for_hardware_aec(monkeypatch):
    monkeypatch.setattr(
        TTSNode,
        '_alsa_playback_devices',
        staticmethod(
            lambda: [
                ('plughw:0,0', 'card 0: ReSpeaker [ReSpeaker Lite], device 0: USB Audio'),
                ('plughw:2,0', 'card 2: Speaker [USB Speaker], device 0: USB Audio'),
            ]
        ),
    )

    assert TTSNode.resolve_alsa_device('plughw:0,0') == 'plughw:0,0'


def test_auto_prefers_separate_usb_playback_device(monkeypatch):
    monkeypatch.setattr(
        TTSNode,
        '_alsa_playback_devices',
        staticmethod(
            lambda: [
                ('plughw:0,0', 'card 0: ReSpeaker [ReSpeaker Lite], device 0: USB Audio'),
                ('plughw:3,0', 'card 3: Device [USB Audio Device], device 0: USB Audio'),
            ]
        ),
    )

    assert TTSNode.resolve_alsa_device('auto') == 'plughw:3,0'


def test_explicit_nonlegacy_output_override_is_preserved(monkeypatch):
    monkeypatch.setattr(
        TTSNode,
        '_alsa_playback_devices',
        staticmethod(lambda: []),
    )

    assert TTSNode.resolve_alsa_device('plughw:4,0') == 'plughw:4,0'
