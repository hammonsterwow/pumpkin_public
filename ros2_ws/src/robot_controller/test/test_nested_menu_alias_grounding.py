from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_postprocess import reconcile_explicit_order_evidence


def test_vanilla_latte_does_not_ground_phantom_cafe_latte_item():
    text = "바닐라라떼 한 잔이에요."
    result = {
        "intent": "ORDER",
        "items": [
            {
                "item_id": 0,
                "menu": "바닐라라떼",
                "temperature": None,
                "quantity": 1,
                "missing_slots": ["temperature"],
            },
            {
                "item_id": 1,
                "menu": "카페라떼",
                "temperature": None,
                "quantity": 1,
                "missing_slots": ["temperature"],
            },
        ],
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
    }

    slots = extract_explicit_slots(text)
    changed = reconcile_explicit_order_evidence(result, slots)

    assert slots["menus"] == ["바닐라라떼"]
    assert changed is True
    assert len(result["items"]) == 1
    assert result["items"][0]["menu"] == "바닐라라떼"
    assert result["items"][0]["quantity"] == 1
    assert result["ungrounded_extra_items"][0]["menu"] == "카페라떼"
