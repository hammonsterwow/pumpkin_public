from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.dialogue_slots import extract_explicit_slots


def make_node():
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = "ORDER_CORRECTION"
    node.session_id = "test-session"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "레몬에이드",
                "temperature": "ICE",
                "quantity": 3,
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


def make_nlu(text):
    slots = extract_explicit_slots(text)
    return {
        "text": text,
        "intent": "ORDER",
        "confidence": 1.0,
        "needs_reprompt": True,
        "order_status": "INCOMPLETE",
        "items": [
            {
                "item_id": 0,
                "menu": None,
                "temperature": None,
                "quantity": slots.get("quantity"),
            }
        ],
        "explicit_slots": slots,
    }


def test_logged_three_to_five_quantity_correction_updates_production_order():
    node = make_node()

    result = node.make_decision(make_nlu("세 잔 말고 다섯 잔 주세요."))

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "order_corrected"
    assert result["nlu_result"]["explicit_slots"]["quantity"] == 5
    assert result["nlu_result"]["explicit_slots"]["correction"] == {
        "slot": "quantity",
        "from": 3,
        "to": 5,
    }
    assert node.current_order["items"][0]["menu"] == "레몬에이드"
    assert node.current_order["items"][0]["temperature"] == "ICE"
    assert node.current_order["items"][0]["quantity"] == 5
