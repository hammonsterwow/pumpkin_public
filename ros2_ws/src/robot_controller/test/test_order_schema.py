from robot_controller.order_schema import build_order_schema, extract_items


def test_extracts_three_supported_order_items_without_collapsing():
    raw = {
        "items": [
            {"menu": "아메리카노", "temperature": "ICE", "quantity": 2},
            {"menu": "카페라떼", "temperature": "HOT", "quantity": 1},
            {"menu": "딸기스무디", "temperature": "ICE", "quantity": 1},
        ]
    }

    items = extract_items(raw)

    assert len(items) == 3
    assert items[0]["item_id"] == 0
    assert items[1]["menu"] == "카페라떼"
    assert items[2]["quantity"] == 1


def test_marks_missing_slots_and_requires_reprompt():
    items = extract_items({"items": [{"menu": "아메리카노", "quantity": 2}]})
    order = build_order_schema(
        intent="ORDER",
        confidence=0.96,
        items=items,
        session_id="session-test",
    )

    assert order["order_status"] == "INCOMPLETE"
    assert order["needs_reprompt"] is True
    assert order["items"][0]["missing_slots"] == ["temperature"]


def test_supports_legacy_single_item_fields_during_migration():
    items = extract_items({
        "menu": "아메리카노",
        "temperature": "ICE",
        "quantity": 2,
    })

    assert items == [{
        "item_id": 0,
        "menu": "아메리카노",
        "temperature": "ICE",
        "quantity": 2,
        "missing_slots": [],
        "validation_errors": [],
    }]


def test_normalizes_menu_alias_and_applies_cold_only_default():
    items = extract_items({
        "items": [
            {
                "menu": "레모네이드",
                "temperature": "NONE",
                "quantity": "한 잔",
            }
        ]
    })

    assert items == [{
        "item_id": 0,
        "menu": "레몬에이드",
        "temperature": "ICE",
        "quantity": 1,
        "missing_slots": [],
        "validation_errors": [],
    }]


def test_rejects_temperature_not_allowed_for_menu():
    items = extract_items({
        "items": [
            {"menu": "딸기스무디", "temperature": "HOT", "quantity": 1}
        ]
    })
    order = build_order_schema(
        intent="ORDER",
        confidence=0.99,
        items=items,
        session_id="session-test",
    )

    assert order["order_status"] == "INVALID"
    assert items[0]["validation_errors"] == [
        "unsupported_temperature_for_menu"
    ]


def test_rejects_unsupported_menu_and_quantity_out_of_range():
    items = extract_items({
        "items": [
            {"menu": "에스프레소", "temperature": "HOT", "quantity": 21}
        ]
    })

    assert items[0]["menu"] is None
    assert items[0]["quantity"] is None
    assert items[0]["validation_errors"] == [
        "unsupported_menu",
        "quantity_must_be_between_1_and_20",
    ]
