import pytest

from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_postprocess import (
    reconcile_explicit_order_evidence,
    recover_fuzzy_menu_evidence,
)


def _single_item_result(
    menu="카페라떼",
    *,
    intent="ORDER",
    intent_confidence=0.999,
    menu_confidence=0.9999,
    active_confidence=0.9999,
):
    return {
        "intent": intent,
        "intent_confidence": intent_confidence,
        "items": [
            {
                "item_id": 0,
                "menu": menu,
                "temperature": None,
                "quantity": None,
                "confidence": {
                    "active": active_confidence,
                    "menu": menu_confidence,
                },
                "missing_slots": ["temperature", "quantity"],
            }
        ],
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
    }


@pytest.mark.parametrize(
    "text",
    [
        "카페라 때 따뜻하게 세 잔 주세요",
        "가채라 때 세 잔 주세요",
        "하페라때",
        "까훼라때",
    ],
)
def test_recovers_dialectal_cafe_latte_only_when_model_agrees(text):
    slots = extract_explicit_slots(text)
    assert slots.get("menu") is None

    result = _single_item_result()
    recovery = recover_fuzzy_menu_evidence(text, result, slots)

    assert recovery is not None
    assert recovery["menu"] == "카페라떼"
    assert recovery["score"] >= 0.80
    assert recovery["margin"] >= 0.12
    assert slots["menu"] == "카페라떼"
    assert slots["menus"] == ["카페라떼"]

    changed = reconcile_explicit_order_evidence(result, slots)
    assert changed is True
    assert result["items"][0]["menu"] == "카페라떼"


def test_does_not_rewrite_raw_text_or_override_exact_menu_evidence():
    text = "카페라떼 세 잔 주세요"
    slots = extract_explicit_slots(text)
    result = _single_item_result()

    recovery = recover_fuzzy_menu_evidence(text, result, slots)

    assert recovery is None
    assert text == "카페라떼 세 잔 주세요"
    assert slots["menu"] == "카페라떼"


def test_existing_short_latte_alias_stays_on_exact_grounding_path():
    text = "하페라떼"
    slots = extract_explicit_slots(text)
    result = _single_item_result()

    assert slots["menu"] == "카페라떼"
    assert recover_fuzzy_menu_evidence(text, result, slots) is None


@pytest.mark.parametrize(
    "text",
    [
        "갑자기 랍데이",
        "여기 엉덩이가 있다",
        "카페라면 주세요",
    ],
)
def test_rejects_unrelated_or_only_superficially_similar_text(text):
    slots = extract_explicit_slots(text)
    result = _single_item_result()

    recovery = recover_fuzzy_menu_evidence(text, result, slots)

    assert recovery is None
    assert slots.get("menu") is None


def test_rejects_fuzzy_match_when_nlu_menu_confidence_is_not_high_enough():
    text = "하페라때"
    slots = extract_explicit_slots(text)
    result = _single_item_result(menu_confidence=0.97)

    assert recover_fuzzy_menu_evidence(text, result, slots) is None
    assert slots.get("menu") is None


def test_rejects_fuzzy_match_when_nlu_prediction_disagrees_with_best_match():
    text = "하페라때"
    slots = extract_explicit_slots(text)
    result = _single_item_result(menu="바닐라라떼")

    assert recover_fuzzy_menu_evidence(text, result, slots) is None
    assert slots.get("menu") is None
