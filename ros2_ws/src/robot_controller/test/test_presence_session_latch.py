from __future__ import annotations

from types import SimpleNamespace

from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


def make_node(state: str):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "presence-session"
    node.current_order = {"items": [{"menu": "아메리카노"}]}
    node.waiting_for = {"item_id": 0, "slot": "quantity"}
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.human_presence_initialized = True
    node.last_human_presence = True
    node._customer_exit_seen = False
    node.reset_retry_counts = lambda: None
    return node


def test_presence_bounces_do_not_change_active_order_session():
    node = make_node("ORDER_LISTEN")
    greetings = []
    node.handle_human_detected = lambda: greetings.append("greet")

    node.human_presence_callback(SimpleNamespace(data=False))
    node.human_presence_callback(SimpleNamespace(data=True))
    node.human_presence_callback(SimpleNamespace(data=False))
    node.human_presence_callback(SimpleNamespace(data=True))

    assert node.state == "ORDER_LISTEN"
    assert node.current_order is not None
    assert greetings == []


def test_completed_order_requires_false_then_true_for_next_customer():
    node = make_node("WAIT_CUSTOMER_EXIT")
    greetings = []
    node.handle_human_detected = lambda: greetings.append("greet")
    node.get_logger = lambda: SimpleNamespace(info=lambda *_args, **_kwargs: None)

    # Same completed customer is still standing there: no new greeting.
    node.human_presence_callback(SimpleNamespace(data=True))
    assert greetings == []
    assert node.state == "WAIT_CUSTOMER_EXIT"

    # Customer leaves: arm the handoff, still no greeting.
    node.human_presence_callback(SimpleNamespace(data=False))
    assert node._customer_exit_seen is True
    assert greetings == []

    # Only the next presence starts another session.
    node.human_presence_callback(SimpleNamespace(data=True))
    assert node._customer_exit_seen is False
    assert greetings == ["greet"]
    assert node.state == "IDLE"


def test_presence_true_without_exit_never_restarts_completed_customer():
    node = make_node("WAIT_CUSTOMER_EXIT")
    greetings = []
    node.handle_human_detected = lambda: greetings.append("greet")
    node.get_logger = lambda: SimpleNamespace(info=lambda *_args, **_kwargs: None)

    for _ in range(5):
        node.human_presence_callback(SimpleNamespace(data=True))

    assert greetings == []
    assert node.state == "WAIT_CUSTOMER_EXIT"
