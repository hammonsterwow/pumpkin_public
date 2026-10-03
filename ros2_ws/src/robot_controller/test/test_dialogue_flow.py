from robot_controller.decision_node import DecisionNode
from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.response_manager import ResponseManager


def make_decision_node():
    node = DecisionNode.__new__(DecisionNode)
    node.state = "ORDER_LISTEN"
    node.session_id = "test-session"
    node.current_order = None
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def test_extracts_short_temperature_and_quantity_answers():
    assert extract_explicit_slots("따뜻하게요") == {
        "menu": None,
        "temperature": "HOT",
        "quantity": None,
    }
    assert extract_explicit_slots("온으로요") == {
        "menu": None,
        "temperature": "HOT",
        "quantity": None,
    }
    assert extract_explicit_slots("두 잔이요") == {
        "menu": None,
        "temperature": None,
        "quantity": 2,
    }
    assert extract_explicit_slots("스무 잔이요") == {
        "menu": None,
        "temperature": None,
        "quantity": 20,
    }


def test_keeps_item_query_order_and_targets_first_missing_slot_per_item():
    node = make_decision_node()
    items = [
        {
            "item_id": 0,
            "menu": "아메리카노",
            "quantity": 1,
            "temperature": None,
        },
        {
            "item_id": 1,
            "menu": "카페라떼",
            "quantity": None,
            "temperature": None,
        },
    ]

    assert node.next_missing_target(items) == {
        "item_id": 0,
        "slot": "temperature",
    }


def test_merges_short_followup_into_waiting_item_only():
    node = make_decision_node()
    node.waiting_for = {"item_id": 1, "slot": "temperature"}
    current = [
        {
            "item_id": 0,
            "menu": "아메리카노",
            "quantity": 1,
            "temperature": "ICE",
            "missing_slots": [],
            "validation_errors": [],
        },
        {
            "item_id": 1,
            "menu": "카페라떼",
            "quantity": 1,
            "temperature": None,
            "missing_slots": ["temperature"],
            "validation_errors": [],
        },
    ]
    incoming = [
        {
            "item_id": 0,
            "menu": None,
            "quantity": None,
            "temperature": "HOT",
            "missing_slots": ["menu", "quantity"],
            "validation_errors": [],
        }
    ]

    merged = node.merge_order_items(current, incoming)

    assert merged[0]["temperature"] == "ICE"
    assert merged[1]["temperature"] == "HOT"
    assert merged[1]["missing_slots"] == []


def test_waiting_response_contains_context_but_no_finished_sentence():
    node = make_decision_node()
    items = [
        {
            "item_id": 0,
            "menu": "아메리카노",
            "quantity": 1,
            "temperature": None,
        }
    ]
    waiting_for = {"item_id": 0, "slot": "temperature"}

    args = node.response_args_for_waiting(waiting_for, items)
    decision = node.order_decision(
        "ASK_TEMPERATURE",
        "ask_temperature",
        "missing_temperature",
        {"items": items},
        {"text": "아메리카노 하나요"},
        response_args=args,
    )

    assert "speech" not in decision
    assert decision["response_key"] == "ask_temperature"
    assert decision["response_args"] == {
        "item_id": 0,
        "slot": "temperature",
        "menu": "아메리카노",
    }
    response = ResponseManager().render(decision)
    assert response["speech"] == (
        "아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?"
    )


def test_multi_item_correction_requires_menu_target():
    node = make_decision_node()
    current = [
        {"item_id": 0, "menu": "아메리카노"},
        {"item_id": 1, "menu": "카페라떼"},
    ]
    incoming = [
        {"item_id": 0, "menu": None, "temperature": "ICE", "quantity": None}
    ]

    assert node.correction_target_is_ambiguous(current, incoming) is True
