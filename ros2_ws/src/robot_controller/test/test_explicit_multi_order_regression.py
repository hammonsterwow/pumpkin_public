from robot_controller.dialogue_slots import (
    extract_explicit_slots,
    extract_menus,
    extract_quantity,
)


def make_nlu_result(text: str):
    return {
        "schema_version": "1.0",
        "model_name": "structure_b_item_query_decoder",
        "text": text,
        "intent": "ORDER",
        "intent_confidence": 0.9999,
        "order_status": "INCOMPLETE",
        "order_status_confidence": 0.9998,
        "items": [
            {
                "item_id": 0,
                "menu": "딸기스무디",
                "temperature": "ICE",
                "quantity": None,
                "confidence": {
                    "active": 1.0,
                    "menu": 0.9731,
                    "temperature": 0.9976,
                    "quantity": 1.0,
                },
                "missing_slots": ["quantity"],
            },
            {
                "item_id": 1,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": 1,
                "confidence": {
                    "active": 0.9998,
                    "menu": 1.0,
                    "temperature": 0.9994,
                    "quantity": 0.9983,
                },
                "missing_slots": [],
            },
        ],
        "needs_reprompt": True,
        "device": "cpu",
        "latency_ms": 1.0,
    }


def test_quantity_does_not_match_se_inside_juseyo():
    assert extract_quantity("주세요") is None
    assert extract_quantity("메뉴를 말씀해 주세요") is None
    assert extract_quantity("세 잔 주세요") == 3
    assert extract_quantity("세 개요") == 3


def test_each_quantity_expression_and_multi_menu_order():
    text = "레모네이드랑 아메리카노 차갑게 하나씩 주세요"
    slots = extract_explicit_slots(text)

    assert extract_menus(text) == ["레몬에이드", "아메리카노"]
    assert slots["menu"] == "레몬에이드"
    assert slots["menus"] == ["레몬에이드", "아메리카노"]
    assert slots["temperature"] == "ICE"
    assert slots["quantity"] == 1
    assert slots["apply_to_all_items"] is True


def test_nested_latte_alias_does_not_create_phantom_cafe_latte():
    text = "바닐라라떼 한 잔이에요."
    slots = extract_explicit_slots(text)

    assert extract_menus(text) == ["바닐라라떼"]
    assert slots["menu"] == "바닐라라떼"
    assert slots["menus"] == ["바닐라라떼"]
    assert slots["quantity"] == 1


def test_real_cafe_latte_after_vanilla_latte_is_still_preserved():
    text = "바닐라라떼 한 잔이랑 카페라떼 한 잔 주세요"

    assert extract_menus(text) == ["바닐라라떼", "카페라떼"]


def test_short_latte_alias_still_means_cafe_latte():
    assert extract_menus("라떼 한 잔 주세요") == ["카페라떼"]


def test_live_stt_cafe_latte_spacing_variant_is_grounded():
    assert extract_menus("카페라 때 한 잔 주세요") == ["카페라떼"]


def test_explicit_multi_menu_overrides_wrong_model_menu(pipeline):
    text = "저 레모네이드랑 아메리카노 차갑게 하나씩 주세요"
    decision, action = pipeline.say(text, make_nlu_result(text))

    assert decision["decision"] == "CONFIRM_ORDER"
    assert action["decision"] == "CONFIRM_ORDER"
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in decision["order"]["items"]
    ] == [
        ("레몬에이드", "ICE", 1),
        ("아메리카노", "ICE", 1),
    ]
    assert all(not item["missing_slots"] for item in decision["order"]["items"])
    assert "레몬에이드" in action["tts"]
    assert "아메리카노" in action["tts"]
