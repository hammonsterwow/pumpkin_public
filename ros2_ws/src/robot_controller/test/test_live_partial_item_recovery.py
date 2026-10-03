from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_postprocess import reconcile_explicit_order_evidence
from robot_controller.order_schema import extract_items


def test_live_two_quantities_one_menu_preserves_missing_first_menu():
    text = "한 잔이랑 바닐라라떼 15 잔."
    slots = extract_explicit_slots(text)

    assert slots["menu"] == "바닐라라떼"
    assert slots["quantity"] == 15
    assert slots["item_hints"] == [
        {"menu": None, "temperature": None, "quantity": 1},
        {"menu": "바닐라라떼", "temperature": None, "quantity": 15},
    ]

    result = {
        "text": text,
        "intent": "ORDER",
        "items": [
            {"item_id": 0, "menu": "아메리카노", "temperature": "ICE", "quantity": 1},
            {"item_id": 1, "menu": "바닐라라떼", "temperature": "HOT", "quantity": 1},
        ],
        "order_status": "VALID",
        "needs_reprompt": False,
    }

    assert reconcile_explicit_order_evidence(result, slots) is True
    assert result["literal_item_hints_applied"] is True
    assert result["order_status"] == "INCOMPLETE"

    normalized = extract_items(result)
    assert normalized[0]["menu"] is None
    assert normalized[0]["quantity"] == 1
    assert normalized[0]["missing_slots"] == ["menu", "temperature"]
    assert normalized[1]["menu"] == "바닐라라떼"
    assert normalized[1]["temperature"] is None
    assert normalized[1]["quantity"] == 15


def test_normal_single_item_does_not_create_partial_hint():
    slots = extract_explicit_slots("바닐라라떼 15잔 주세요.")

    assert slots["menu"] == "바닐라라떼"
    assert slots["quantity"] == 15
    assert "item_hints" not in slots
