from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.multi_item_span_grounding import recover_multi_item_span_evidence
from robot_controller.nlu_postprocess import reconcile_explicit_order_evidence


def _model_item(item_id, menu, temperature, quantity, *, menu_confidence=0.9999):
    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "confidence": {
            "active": 0.9999,
            "menu": menu_confidence,
            "temperature": 0.999,
            "quantity": 0.999,
        },
        "missing_slots": [],
    }


def _result(items, *, intent_confidence=1.0):
    return {
        "intent": "ORDER",
        "intent_confidence": intent_confidence,
        "items": items,
        "order_status": "VALID",
        "needs_reprompt": False,
    }


def test_recovers_distorted_second_menu_inside_quantity_anchored_span():
    text = "아이스 아메리카노 두 잔이랑 따뜻한 칼테라 때 한 잔 주세요"
    slots = extract_explicit_slots(text)
    result = _result(
        [
            _model_item(0, "아메리카노", "ICE", 2),
            _model_item(1, "카페라떼", "HOT", 1),
        ]
    )

    recovery = recover_multi_item_span_evidence(text, result, slots)

    assert recovery is not None
    assert recovery["item_count"] == 2
    assert recovery["partial_item_indexes"] == []
    assert len(recovery["fuzzy_recoveries"]) == 1
    assert recovery["fuzzy_recoveries"][0]["item_index"] == 1
    assert recovery["fuzzy_recoveries"][0]["menu"] == "카페라떼"
    assert slots["item_hints"] == [
        {"menu": "아메리카노", "temperature": "ICE", "quantity": 2},
        {"menu": "카페라떼", "temperature": "HOT", "quantity": 1},
    ]

    assert reconcile_explicit_order_evidence(result, slots) is True
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in result["items"]
    ] == [
        ("아메리카노", "ICE", 2),
        ("카페라떼", "HOT", 1),
    ]


def test_keeps_second_item_partial_when_fuzzy_menu_is_not_safe():
    text = "아이스 아메리카노 두 잔이랑 따뜻한 완전히 다른 말 한 잔 주세요"
    slots = extract_explicit_slots(text)
    result = _result(
        [
            _model_item(0, "아메리카노", "ICE", 2),
            _model_item(1, "카페라떼", "HOT", 1),
        ]
    )

    recovery = recover_multi_item_span_evidence(text, result, slots)

    assert recovery is not None
    assert recovery["fuzzy_recoveries"] == []
    assert recovery["partial_item_indexes"] == [1]
    assert slots["item_hints"] == [
        {"menu": "아메리카노", "temperature": "ICE", "quantity": 2},
        {"menu": None, "temperature": "HOT", "quantity": 1},
    ]

    assert reconcile_explicit_order_evidence(result, slots) is True
    assert result["items"][0]["menu"] == "아메리카노"
    assert result["items"][0]["quantity"] == 2
    assert result["items"][1]["menu"] is None
    assert result["items"][1]["temperature"] == "HOT"
    assert result["items"][1]["quantity"] == 1
    assert result["order_status"] == "INCOMPLETE"
    assert result["needs_reprompt"] is True


def test_partial_item_survives_even_when_model_did_not_activate_second_query():
    text = "아이스 아메리카노 두 잔이랑 따뜻한 이상한 음료 한 잔 주세요"
    slots = extract_explicit_slots(text)
    result = _result([
        _model_item(0, "아메리카노", "ICE", 2),
    ])

    recovery = recover_multi_item_span_evidence(text, result, slots)

    assert recovery is not None
    assert recovery["partial_item_indexes"] == [1]
    assert reconcile_explicit_order_evidence(result, slots) is True
    assert len(result["items"]) == 2
    assert result["items"][1]["menu"] is None
    assert result["items"][1]["temperature"] == "HOT"
    assert result["items"][1]["quantity"] == 1


def test_does_not_create_multi_items_without_one_exact_menu_anchor():
    text = "오늘 두 잔이랑 내일 한 잔 이야기했어"
    slots = extract_explicit_slots(text)
    result = _result(
        [
            _model_item(0, "아메리카노", "ICE", 2),
            _model_item(1, "카페라떼", "HOT", 1),
        ]
    )

    assert recover_multi_item_span_evidence(text, result, slots) is None
    assert "item_hints" not in slots


def test_does_not_split_quantity_correction_into_two_drinks():
    text = "아메리카노 두 잔 말고 한 잔으로 수정할게요"
    slots = extract_explicit_slots(text)
    result = _result([
        _model_item(0, "아메리카노", "ICE", 1),
    ])

    assert slots.get("correction") is not None
    assert recover_multi_item_span_evidence(text, result, slots) is None
    assert "item_hints" not in slots


def test_requires_high_order_intent_confidence_before_multi_item_recovery():
    text = "아이스 아메리카노 두 잔이랑 따뜻한 칼테라 때 한 잔 주세요"
    slots = extract_explicit_slots(text)
    result = _result(
        [
            _model_item(0, "아메리카노", "ICE", 2),
            _model_item(1, "카페라떼", "HOT", 1),
        ],
        intent_confidence=0.8,
    )

    assert recover_multi_item_span_evidence(text, result, slots) is None
    assert "item_hints" not in slots
