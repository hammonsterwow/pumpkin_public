from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_node import (
    normalize_quantity_homophone,
    normalize_standalone_confirmation_result,
)


def base_result():
    return {
        "intent": "ORDER",
        "intent_confidence": 0.75,
        "order_status": "INCOMPLETE",
        "items": [
            {
                "item_id": 0,
                "menu": None,
                "temperature": None,
                "quantity": 4,
            }
        ],
        "needs_reprompt": True,
        "explicit_slots": {"quantity": 4},
    }


def test_bare_ne_is_affirmation_not_quantity_four():
    result = base_result()

    assert normalize_standalone_confirmation_result("네", result) is True
    assert result["intent"] == "AFFIRM"
    assert result["order_status"] == "NONE"
    assert result["items"] == []
    assert result["needs_reprompt"] is False
    assert "explicit_slots" not in result


def test_other_standalone_confirmation_phrases_are_deterministic():
    for text in ("예", "응", "맞아요"):
        result = base_result()
        assert normalize_standalone_confirmation_result(text, result) is True
        assert result["intent"] == "AFFIRM"

    for text in ("아니요", "아뇨"):
        result = base_result()
        assert normalize_standalone_confirmation_result(text, result) is True
        assert result["intent"] == "DENY"


def test_quantity_phrase_ne_jan_is_not_rewritten_as_confirmation():
    result = base_result()

    assert normalize_standalone_confirmation_result("네 잔 주세요", result) is False
    assert result["intent"] == "ORDER"
    assert result["items"][0]["quantity"] == 4


def test_quantity_homophone_normalizes_observed_repeated_transcript():
    assert normalize_quantity_homophone("세전! 세전이요.") == "세 잔! 세 잔이요."


def test_quantity_homophone_normalizes_short_polite_answer():
    assert normalize_quantity_homophone("세 전이요") == "세 잔이요"


def test_quantity_homophone_normalizes_live_jjan_unit_answers():
    assert normalize_quantity_homophone("여덟 짠") == "여덟 잔"
    assert normalize_quantity_homophone("아홉 짠이요") == "아홉 잔이요"
    assert normalize_quantity_homophone("8짠이에요") == "8 잔이에요"


def test_quantity_homophone_normalizes_jjan_inside_full_order():
    normalized = normalize_quantity_homophone("아메리카노 아홉 짠 주세요")

    assert normalized == "아메리카노 아홉 잔 주세요"
    assert extract_explicit_slots(normalized)["quantity"] == 9


def test_quantity_homophone_does_not_turn_standalone_jjan_into_quantity():
    assert normalize_quantity_homophone("짠!") == "짠!"
    assert normalize_quantity_homophone("짠 하고 인사했어요") == "짠 하고 인사했어요"


def test_quantity_homophone_does_not_rewrite_unrelated_or_correct_text():
    assert normalize_quantity_homophone("세전 소득을 알려줘") == "세전 소득을 알려줘"
    assert normalize_quantity_homophone("세 잔이요") == "세 잔이요"
