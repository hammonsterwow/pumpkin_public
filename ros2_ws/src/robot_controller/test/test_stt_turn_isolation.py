import threading

from robot_controller.stt_node_safe import SafeSTTNode


def make_guard_node(active_token=42):
    node = SafeSTTNode.__new__(SafeSTTNode)
    node._lock = threading.Lock()
    node._shutdown_requested = False
    node._start_token = active_token
    node._active_capture_token = active_token
    node._active_cancel_event = threading.Event()
    node._busy = True
    return node


def test_current_capture_requires_matching_owner_token_and_event():
    node = make_guard_node(42)
    event = node._active_cancel_event

    assert node._capture_is_current(42, event) is True

    node._start_token = 43
    assert node._capture_is_current(42, event) is False


def test_cancelled_capture_can_never_be_current_again():
    node = make_guard_node(42)
    event = node._active_cancel_event

    event.set()
    assert node._capture_is_current(42, event) is False


def test_stale_thread_cannot_release_newer_capture_busy_state():
    node = make_guard_node(43)
    newer_event = node._active_cancel_event

    # Simulate an old token-42 thread reaching finally after token 43 already
    # owns the microphone. The old cleanup must not set _busy=False.
    assert node._release_capture_owner(42) is False
    assert node._busy is True
    assert node._active_capture_token == 43
    assert node._active_cancel_event is newer_event

    assert node._release_capture_owner(43) is True
    assert node._busy is False
    assert node._active_capture_token is None
    assert node._active_cancel_event is None
