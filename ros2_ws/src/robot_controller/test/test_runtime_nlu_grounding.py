from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_postprocess import (
    clear_unexpressed_quantity_predictions,
    clear_unexpressed_temperature_predictions,
    ground_order_items_to_explicit_evidence,
)


def model_item(menu="아메리카노", temperature="ICE", quantity=1):
    return {
        "item_id": 0,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": [],
        "confidence": {
            "active": 0.9999,
            "menu": 0.9999,
            "temperature": 0.9999,
            "quantity": 0.9999,
        },
    }


def make_order(items):
    return {
        "intent": "ORDER",
        "order_status": "VALID",
        "needs_reprompt": False,
        "items": items,
    }


def test_ambient_aa_interjection_is_not_order_evidence():
    slots = extract_explicit_slots(
        "지금 끝하고 있을 수 있어요? 아아 언니 뭐 끄고 계세요? 안녕하십시오."
    )

    assert slots["menu"] is None
    assert slots["temperature"] is None
    assert slots["quantity"] is None


def test_real_aa_order_alias_still_works():
    slots = extract_explicit_slots("아아 한 잔 주세요")

    assert slots["menu"] == "아메리카노"
    assert slots["temperature"] == "ICE"
    assert slots["quantity"] == 1


def test_background_sentence_cannot_create_phantom_model_items():
    result = make_order([
        model_item(),
        {**model_item(), "item_id": 1},
        {**model_item(), "item_id": 2},
    ])
    slots = extract_explicit_slots("제발 괜찮아.")

    changed = ground_order_items_to_explicit_evidence(result, slots)

    assert changed is True
    assert result["items"] == []
    assert result["order_status"] == "UNPARSABLE"
    assert result["needs_reprompt"] is True
    assert len(result["ungrounded_model_items"]) == 3


def test_single_spoken_menu_collapses_three_phantom_queries():
    result = make_order([
        model_item(quantity=1),
        {**model_item(quantity=4), "item_id": 1},
        {**model_item(quantity=2), "item_id": 2},
    ])
    slots = extract_explicit_slots("아이스 아메리카노")

    assert ground_order_items_to_explicit_evidence(result, slots) is True
    clear_unexpressed_temperature_predictions(result, slots)
    clear_unexpressed_quantity_predictions(result, slots)

    assert len(result["items"]) == 1
    assert result["items"][0]["menu"] == "아메리카노"
    assert result["items"][0]["temperature"] == "ICE"
    assert result["items"][0]["quantity"] is None
    assert result["items"][0]["missing_slots"] == ["quantity"]


def test_quantity_only_followup_does_not_inherit_model_menu():
    result = make_order([model_item(menu="아메리카노", temperature="ICE", quantity=3)])
    slots = extract_explicit_slots("세 잔이요")

    assert ground_order_items_to_explicit_evidence(result, slots) is True

    assert len(result["items"]) == 1
    assert result["items"][0]["menu"] is None
    assert result["items"][0]["temperature"] is None
    assert result["items"][0]["quantity"] == 3


def test_natural_order_negative_is_cancel_command():
    resolver = DialogueActResolver()

    assert resolver.resolve_command({"text": "아메리카노 주문 안 할 거예요."}) == "CANCEL"
