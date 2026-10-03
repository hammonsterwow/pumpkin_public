from copy import deepcopy

from robot_controller.response_manager import ResponseManager


def test_renderer_does_not_mutate_decision_payload():
    manager = ResponseManager()
    decision = {
        "decision": "ASK_QUANTITY",
        "response_key": "ask_quantity",
        "response_args": {"item_id": 1, "menu": "카페라떼"},
        "waiting_for": {"item_id": 1, "slot": "quantity"},
    }
    original = deepcopy(decision)

    response = manager.render(decision)

    assert decision == original
    assert "speech" not in decision
    assert response["speech"] == "카페라떼는 몇 잔 주문하시겠어요?"
    assert response["display_text"] == "카페라떼 수량을 선택해 주세요"


def test_item_confirmation_and_quantity_are_separate_turns():
    context = {
        "response_args": {
            "item_id": 0,
            "slot": "quantity",
            "menu": "아메리카노",
        },
        "waiting_for": {"item_id": 0, "slot": "quantity"},
        "order": {
            "items": [
                {
                    "item_id": 0,
                    "menu": "아메리카노",
                    "temperature": "ICE",
                    "quantity": None,
                }
            ]
        },
    }

    confirm = ResponseManager().render({
        **context,
        "decision": "CONFIRM_ITEM",
        "response_key": "confirm_item",
    })
    quantity = ResponseManager().render({
        **context,
        "decision": "ASK_QUANTITY",
        "response_key": "ask_quantity",
    })

    assert confirm["speech"] == "아이스 아메리카노 맞으신가요?"
    assert quantity["speech"] == "아이스 아메리카노는 몇 잔 주문하시겠어요?"
    assert quantity["display_text"] == "아이스 아메리카노 수량을 선택해 주세요"


def test_item_confirmation_denied_asks_for_order_again():
    response = ResponseManager().render({
        "decision": "REORDER_REQUEST",
        "response_key": "ask_order",
    })

    assert response["speech"] == "무엇을 주문하시겠어요?"
    assert response["display_text"] == "무엇을 주문하시겠어요?"


def test_confirm_order_renders_all_items_in_order():
    response = ResponseManager().render({
        "decision": "CONFIRM_ORDER",
        "response_key": "confirm_order",
        "response_args": {},
        "order": {
            "items": [
                {
                    "item_id": 0,
                    "menu": "아메리카노",
                    "temperature": "HOT",
                    "quantity": 1,
                },
                {
                    "item_id": 1,
                    "menu": "카페라떼",
                    "temperature": "ICE",
                    "quantity": 2,
                },
            ]
        },
    })

    assert response["speech"] == (
        "따뜻한 아메리카노 1잔, 아이스 카페라떼 2잔 맞으신가요?"
    )
    assert response["display_text"] == (
        "따뜻한 아메리카노 1잔, 아이스 카페라떼 2잔"
    )


def test_unknown_response_key_uses_safe_fallback():
    response = ResponseManager().render({
        "decision": "UNKNOWN",
        "response_key": "not_registered",
    })

    assert response["speech"] == "주문이나 매장 안내를 도와드릴 수 있어요."
    assert response["display_text"] == response["speech"]


def test_guide_direction_is_rendered_from_structured_context():
    response = ResponseManager().render({
        "decision": "GUIDE_CUSTOMER",
        "response_key": "guide_customer",
        "response_args": {"direction": "LEFT"},
    })

    assert response["speech"] == "왼쪽 방향으로 안내해드릴게요."
