from robot_controller.decision_node_additional_order import AdditionalOrderDecisionNode
from robot_controller.response_manager_order_exception import OrderExceptionAwareResponseManager


def make_node(state="ORDER_LISTEN", current_order=None, waiting_for=None):
    node = AdditionalOrderDecisionNode.__new__(AdditionalOrderDecisionNode)
    node.state = state
    node.session_id = "session-s8"
    node.current_order = current_order
    node.waiting_for = waiting_for
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.correction_target_item_id = None
    return node


def order_result(
    text,
    *,
    menu=None,
    temperature=None,
    quantity=1,
    intent="ORDER",
    confidence=1.0,
):
    item = {
        "item_id": 0,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": [
            slot
            for slot, value in (
                ("menu", menu),
                ("quantity", quantity),
                ("temperature", temperature),
            )
            if value is None
        ],
        "validation_errors": [],
    }
    return {
        "text": text,
        "intent": intent,
        "confidence": confidence,
        "intent_confidence": confidence,
        "needs_reprompt": False,
        "order_status": "VALID" if not item["missing_slots"] else "INCOMPLETE",
        "items": [item],
        "explicit_slots": {
            "menu": menu,
            "menus": [menu] if menu else [],
            "temperature": temperature,
            "quantity": quantity,
        },
    }


def test_hot_strawberry_is_rejected_and_dialogue_restarts_cleanly():
    node = make_node()
    result_input = order_result(
        "따뜻한 딸기스무디 한 잔 주세요.",
        menu="딸기스무디",
        temperature="HOT",
        quantity=1,
    )

    decision = node.make_decision(result_input)
    response = OrderExceptionAwareResponseManager().render(decision)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_key"] == "unsupported_temperature_for_menu"
    assert decision["response_args"]["menu"] == "딸기스무디"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None
    assert node.waiting_for is None
    assert response["speech"] == "딸기스무디는 아이스로만 제공돼요. 다시 주문해 주세요."


def test_hot_lemonade_is_rejected_with_same_policy():
    node = make_node()
    result_input = order_result(
        "따뜻한 레몬에이드 두 잔 주세요.",
        menu="레몬에이드",
        temperature="HOT",
        quantity=2,
    )

    decision = node.make_decision(result_input)
    response = OrderExceptionAwareResponseManager().render(decision)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_args"]["menu"] == "레몬에이드"
    assert response["speech"] == "레몬에이드는 아이스로만 제공돼요. 다시 주문해 주세요."


def test_unsupported_menu_name_is_rejected_even_if_model_hallucinates_supported_item():
    node = make_node()
    result_input = order_result(
        "카푸치노 한 잔 주세요.",
        menu=None,
        temperature=None,
        quantity=1,
    )
    # Simulate the query decoder inventing a supported menu despite no literal
    # supported-menu evidence. S8 must trust the text-level menu policy first.
    result_input["items"] = [
        {
            "item_id": 0,
            "menu": "아메리카노",
            "temperature": None,
            "quantity": 1,
            "missing_slots": ["temperature"],
            "validation_errors": [],
        }
    ]

    decision = node.make_decision(result_input)
    response = OrderExceptionAwareResponseManager().render(decision)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_key"] == "unsupported_menu"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None
    assert response["speech"] == "현재 주문 가능한 메뉴 중에서 골라 말씀해 주세요."


def test_unsupported_compound_latte_is_not_accepted_as_short_cafe_latte_alias():
    node = make_node()
    result_input = order_result(
        "초코라떼 한 잔 주세요.",
        # Current literal extraction can see the embedded short alias "라떼";
        # S8 must still reject the unsupported compound name.
        menu="카페라떼",
        temperature=None,
        quantity=1,
    )

    decision = node.make_decision(result_input)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_key"] == "unsupported_menu"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None


def test_bare_unsupported_menu_is_rejected_when_robot_is_explicitly_asking_menu():
    current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": None,
                "temperature": "ICE",
                "quantity": 2,
                "missing_slots": ["menu"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
    }
    node = make_node(
        state="ASK_MENU",
        current_order=current_order,
        waiting_for={"item_id": 0, "slot": "menu"},
    )
    result_input = {
        "text": "카푸치노요",
        "intent": "UNKNOWN",
        "confidence": 0.8,
        "needs_reprompt": False,
        "order_status": "UNPARSABLE",
        "items": [],
        "explicit_slots": {
            "menu": None,
            "menus": [],
            "temperature": None,
            "quantity": None,
        },
    }

    decision = node.make_decision(result_input)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_key"] == "unsupported_menu"
    assert node.current_order is None
    assert node.state == "ORDER_LISTEN"


def test_hot_answer_to_existing_strawberry_temperature_question_is_rejected():
    current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "딸기스무디",
                "temperature": None,
                "quantity": 1,
                "missing_slots": ["temperature"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
    }
    node = make_node(
        state="ASK_TEMPERATURE",
        current_order=current_order,
        waiting_for={"item_id": 0, "slot": "temperature"},
    )
    result_input = order_result(
        "따뜻하게요.",
        menu=None,
        temperature="HOT",
        quantity=None,
    )

    decision = node.make_decision(result_input)

    assert decision["decision"] == "OUT_OF_POLICY"
    assert decision["response_key"] == "unsupported_temperature_for_menu"
    assert decision["response_args"]["menu"] == "딸기스무디"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None


def test_slot_only_order_without_menu_keeps_existing_missing_menu_flow():
    node = make_node()
    result_input = order_result(
        "아이스 두 잔 주세요.",
        menu=None,
        temperature="ICE",
        quantity=2,
    )

    decision = node.make_decision(result_input)

    assert decision["decision"] == "ASK_MENU"
    assert decision["response_key"] == "ask_menu"
    assert node.state == "ASK_MENU"
    assert node.current_order is not None


def test_supported_hot_americano_is_not_blocked_by_s8_policy():
    node = make_node()
    result_input = order_result(
        "따뜻한 아메리카노 한 잔 주세요.",
        menu="아메리카노",
        temperature="HOT",
        quantity=1,
    )

    decision = node.make_decision(result_input)

    assert decision["decision"] == "CONFIRM_ORDER"
    assert node.state == "ORDER_CONFIRM"
    assert node.current_order["items"][0]["menu"] == "아메리카노"
    assert node.current_order["items"][0]["temperature"] == "HOT"
