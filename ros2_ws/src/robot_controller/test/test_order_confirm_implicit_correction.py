from __future__ import annotations

from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode


def make_node(*, quantity: int = 1):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = "ORDER_CONFIRM"
    node.session_id = "test-session"
    node.current_order = {
        "schema_version": "1.0",
        "session_id": "test-session",
        "intent": "ORDER",
        "confidence": 1.0,
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": quantity,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
        "needs_reprompt": False,
        "original_text": "아이스 아메리카노 한 잔이요.",
        "waiting_for": None,
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def test_repeated_same_menu_with_new_quantity_updates_confirmation_order():
    node = make_node(quantity=1)

    result = node.make_decision(
        {
            "text": "아이스 아메리카노 두 잔이요.",
            "intent": "ORDER",
            "confidence": 1.0,
            "needs_reprompt": False,
            "order_status": "VALID",
            "items": [
                {
                    "item_id": 0,
                    "menu": "아메리카노",
                    "temperature": "ICE",
                    "quantity": 2,
                    "missing_slots": [],
                    "validation_errors": [],
                }
            ],
            "explicit_slots": {
                "menu": "아메리카노",
                "menus": ["아메리카노"],
                "temperature": "ICE",
                "quantity": 2,
            },
        }
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "order_corrected"
    assert result["order"]["items"][0]["quantity"] == 2
    assert node.current_order["items"][0]["quantity"] == 2


def test_bare_quantity_chatter_does_not_mutate_confirmed_item():
    node = make_node(quantity=2)

    result = node.make_decision(
        {
            "text": "귀여워. 아, 한 잔 바보같이 생긴다니까.",
            "intent": "ORDER",
            "confidence": 1.0,
            "needs_reprompt": True,
            "order_status": "INCOMPLETE",
            "items": [
                {
                    "item_id": 0,
                    "menu": None,
                    "temperature": None,
                    "quantity": 1,
                    "missing_slots": ["menu", "temperature"],
                    "validation_errors": [],
                }
            ],
            "explicit_slots": {
                "menu": None,
                "menus": [],
                "temperature": None,
                "quantity": 1,
            },
        }
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "confirmation_required"
    assert result["order"]["items"][0]["quantity"] == 2
    assert node.current_order["items"][0]["quantity"] == 2
