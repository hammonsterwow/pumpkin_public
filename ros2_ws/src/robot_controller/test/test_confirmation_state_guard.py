from copy import deepcopy

from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


def make_node(state="ORDER_CONFIRM"):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "confirmation-guard"
    node.current_order = {
        "schema_version": "1.0",
        "session_id": node.session_id,
        "intent": "ORDER",
        "confidence": 1.0,
        "items": [
            {
                "item_id": 0,
                "menu": "딸기스무디",
                "temperature": "ICE",
                "quantity": 1,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
        "needs_reprompt": False,
        "waiting_for": None,
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.human_presence_initialized = True
    node.last_human_presence = True
    node._customer_exit_seen = False
    return node


def stray_menu_nlu(text="아이스 아메리카노에 맞다고 제가 예상했던 것 같아요."):
    return {
        "text": text,
        "intent": "ORDER",
        "confidence": 1.0,
        "intent_confidence": 1.0,
        "needs_reprompt": False,
        "order_status": "INCOMPLETE",
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
            }
        ],
        "explicit_slots": {
            "menu": "아메리카노",
            "menus": ["아메리카노"],
            "temperature": "ICE",
            "quantity": None,
        },
    }


def test_stray_menu_mention_does_not_append_item_during_order_confirmation():
    node = make_node("ORDER_CONFIRM")
    before = deepcopy(node.current_order)

    decision = node.make_decision(stray_menu_nlu())

    assert decision["decision"] == "CONFIRM_ORDER"
    assert decision["response_key"] == "confirm_order"
    assert decision["reason"] == "confirmation_required"
    assert node.state == "ORDER_CONFIRM"
    assert node.current_order == before
    assert len(node.current_order["items"]) == 1


def test_finish_confirmation_ignores_unrelated_order_prediction():
    node = make_node("WAIT_NEXT_CUSTOMER")
    before = deepcopy(node.current_order)

    decision = node.make_decision(stray_menu_nlu("아메리카노 얘기하고 있었어요."))

    assert decision["decision"] == "ORDER_CONFIRMED"
    assert decision["response_key"] == "ask_next_customer"
    assert decision["reason"] == "finish_confirmation_required"
    assert node.state == "WAIT_NEXT_CUSTOMER"
    assert node.current_order == before
