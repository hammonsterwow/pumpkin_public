from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


class DummyLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


class DummyMessage:
    def __init__(self, data):
        self.data = data


def make_decision_node():
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = "ORDER_CORRECTION"
    node.session_id = "old-session"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "바닐라라떼",
                "temperature": "HOT",
                "quantity": 5,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def test_modify_prompt_uses_short_vad_for_short_correction_answers():
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("MODIFY_ORDER") == "confirm"
    assert (
        OrderHandoffActionNode.resolve_stt_trigger_mode(
            "STT_RETRY",
            previous_mode="confirm",
        )
        == "confirm"
    )


def test_modify_prompt_keeps_head_centered():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)

    rule = node.get_action_rule({"decision": "MODIFY_ORDER"})

    assert rule["head"] == "CENTER"
    assert rule["display"] == "MODIFY_ORDER"


def test_stt_failures_keep_retrying_past_legacy_limit_without_restart():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)
    node.stt_retry_count = 2
    node.max_stt_retries = 2
    requests = []
    cancelled = []
    logger = DummyLogger()
    node.publish_response_request = requests.append
    node.cancel_pending_listen = lambda: cancelled.append(True)
    node.get_logger = lambda: logger

    node.handle_stt_failed("empty")
    node.handle_stt_failed("too_quiet")

    assert cancelled == []
    assert node.stt_retry_count == 4
    assert [request["decision"] for request in requests] == [
        "STT_RETRY",
        "STT_RETRY",
    ]
    assert all(request["response_key"] == "stt_retry" for request in requests)
    assert all(request["response_args"]["unlimited"] is True for request in requests)
    assert requests[-1]["response_args"]["retry_count"] == 4


def test_stt_runtime_error_stops_automatic_retry_loop():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)
    node.stt_retry_count = 5
    requests = []
    cancelled = []
    logger = DummyLogger()
    node.publish_response_request = requests.append
    node.cancel_pending_listen = lambda: cancelled.append(True)
    node.get_logger = lambda: logger

    node.stt_status_callback(
        DummyMessage(
            "error:audio_stream:Error opening InputStream: Invalid number of channels"
        )
    )

    assert cancelled == [True]
    assert node.stt_retry_count == 0
    assert len(requests) == 1
    assert requests[0]["decision"] == "STT_FAILED"
    assert requests[0]["response_key"] == "stt_failed"
    assert requests[0]["response_args"]["fatal"] is True
    assert not any(request["decision"] == "STT_RETRY" for request in requests)


def test_slot_reprompt_past_legacy_limit_preserves_partial_order():
    node = make_decision_node()
    node.state = "ASK_QUANTITY"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "바닐라라떼",
                "temperature": "HOT",
                "quantity": None,
                "missing_slots": ["quantity"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
    }
    node.waiting_for = {"item_id": 0, "slot": "quantity"}
    node.slot_retry_count = 2
    active_order = node.current_order

    decision = node.reprompt_slot(
        {"text": "모르겠어요", "intent": "UNKNOWN"},
        "missing_slot_answer",
    )

    assert decision["decision"] == "REPROMPT"
    assert decision["response_key"] == "ask_quantity"
    assert node.state == "ASK_QUANTITY"
    assert node.current_order is active_order
    assert node.waiting_for == {"item_id": 0, "slot": "quantity"}
    assert node.slot_retry_count == 3


def test_nlu_reprompt_past_legacy_limit_preserves_existing_order():
    node = make_decision_node()
    node.nlu_reprompt_count = 2
    active_order = node.current_order

    decision = node.reprompt_nlu(
        {"text": "음", "intent": "UNKNOWN"},
        "low_confidence",
    )

    assert decision["decision"] == "REPROMPT"
    assert decision["response_key"] == "nlu_reprompt"
    assert node.state == "ORDER_CORRECTION"
    assert node.current_order is active_order
    assert node.nlu_reprompt_count == 3


def test_explicit_restart_still_clears_the_order():
    node = make_decision_node()
    old_session = node.session_id

    decision = node.handle_restart(
        {"text": "처음부터 다시 주문할게요", "intent": "UNKNOWN"}
    )

    assert decision["decision"] == "REORDER_REQUEST"
    assert decision["response_key"] == "restart_order"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None
    assert node.waiting_for is None
    assert node.session_id != old_session
