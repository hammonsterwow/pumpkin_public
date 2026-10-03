from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


def make_node(*, state="ASK_QUANTITY", current_order=None, waiting_for=None):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "session-1"
    node.current_order = current_order
    node.waiting_for = waiting_for
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.pending_customer_context = None
    node.personalized_customer_id = None
    node.greeting_tts_completed = False
    return node


def partial_americano_order():
    return {
        "schema_version": "1.0",
        "session_id": "session-1",
        "intent": "ORDER",
        "confidence": 1.0,
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        "waiting_for": {"item_id": 0, "slot": "quantity"},
    }


def nlu_result(
    text,
    *,
    intent="CANCEL",
    confidence=0.5057,
    explicit_slots=None,
    items=None,
    needs_reprompt=False,
    order_status="NONE",
):
    result = {
        "text": text,
        "intent": intent,
        "confidence": confidence,
        "intent_confidence": confidence,
        "needs_reprompt": needs_reprompt,
        "order_status": order_status,
        "items": list(items or []),
    }
    if explicit_slots is not None:
        result["explicit_slots"] = dict(explicit_slots)
    return result


def test_model_cancel_does_not_override_quantity_answer_in_quantity_state():
    current_order = partial_americano_order()
    node = make_node(
        current_order=current_order,
        waiting_for={"item_id": 0, "slot": "quantity"},
    )

    decision = node.make_decision(
        nlu_result(
            "나 안 하는데 세 잔 인식이 안 돼. 세 잔!",
            explicit_slots={
                "menu": None,
                "menus": [],
                "temperature": None,
                "quantity": 3,
            },
        )
    )

    assert decision["decision"] == "CONFIRM_ORDER"
    assert node.state == "ORDER_CONFIRM"
    assert node.current_order["items"][0]["menu"] == "아메리카노"
    assert node.current_order["items"][0]["temperature"] == "ICE"
    assert node.current_order["items"][0]["quantity"] == 3


def test_model_cancel_without_slot_answer_reprompts_and_keeps_order():
    current_order = partial_americano_order()
    node = make_node(
        current_order=current_order,
        waiting_for={"item_id": 0, "slot": "quantity"},
    )

    decision = node.make_decision(
        nlu_result(
            "왜 인식이 안 되지?",
            confidence=0.99,
            needs_reprompt=False,
        )
    )

    assert decision["decision"] == "REPROMPT"
    assert decision["response_key"] == "ask_quantity"
    assert decision["reason"] == "missing_slot_answer"
    assert node.state == "ASK_QUANTITY"
    assert node.current_order is current_order
    assert node.waiting_for == {"item_id": 0, "slot": "quantity"}


def test_explicit_cancel_text_still_cancels_even_when_model_says_order():
    current_order = partial_americano_order()
    node = make_node(
        current_order=current_order,
        waiting_for={"item_id": 0, "slot": "quantity"},
    )

    decision = node.make_decision(
        nlu_result(
            "주문 취소할게요",
            intent="ORDER",
            confidence=0.99,
            needs_reprompt=False,
        )
    )

    assert decision["decision"] == "CANCEL_ORDER"
    assert decision["response_key"] == "cancel_order"
    assert node.state == "IDLE"
    assert node.current_order is None
    assert node.waiting_for is None


def test_grounded_initial_order_outranks_model_only_cancel_prediction():
    node = make_node(
        state="ORDER_LISTEN",
        current_order=None,
        waiting_for=None,
    )

    decision = node.make_decision(
        nlu_result(
            "아이스 아메리카노 두 잔이요",
            confidence=0.99,
            explicit_slots={
                "menu": "아메리카노",
                "menus": ["아메리카노"],
                "temperature": "ICE",
                "quantity": 2,
            },
        )
    )

    assert decision["decision"] == "CONFIRM_ORDER"
    assert node.state == "ORDER_CONFIRM"
    assert node.current_order["items"][0]["menu"] == "아메리카노"
    assert node.current_order["items"][0]["temperature"] == "ICE"
    assert node.current_order["items"][0]["quantity"] == 2
