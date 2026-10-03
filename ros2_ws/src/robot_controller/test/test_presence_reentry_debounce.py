from types import SimpleNamespace

from robot_controller import decision_node_order_handoff as module
from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


class Logger:
    def info(self, *_args, **_kwargs):
        pass


def make_node():
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.human_presence_initialized = True
    node.last_human_presence = True
    node._absence_started_at = None
    node.state = "ORDER_LISTEN"
    node.get_logger = lambda: Logger()
    node.reset_calls = 0
    node.greeting_calls = 0

    def reset_session():
        node.reset_calls += 1
        node.state = "IDLE"

    def handle_human_detected():
        node.greeting_calls += 1

    node.reset_session = reset_session
    node.handle_human_detected = handle_human_detected
    return node


def test_brief_presence_gap_keeps_same_customer_and_dialogue(monkeypatch):
    node = make_node()
    times = iter([10.0, 10.8])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))

    node.human_presence_callback(SimpleNamespace(data=False))
    node.human_presence_callback(SimpleNamespace(data=True))

    assert node.state == "ORDER_LISTEN"
    assert node.reset_calls == 0
    assert node.greeting_calls == 0
    assert node.last_human_presence is True


def test_sustained_presence_gap_starts_fresh_customer_session(monkeypatch):
    node = make_node()
    times = iter([20.0, 23.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))

    node.human_presence_callback(SimpleNamespace(data=False))
    node.human_presence_callback(SimpleNamespace(data=True))

    assert node.state == "IDLE"
    assert node.reset_calls == 1
    assert node.greeting_calls == 1
    assert node.last_human_presence is True
