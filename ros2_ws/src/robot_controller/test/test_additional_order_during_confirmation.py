from robot_controller.decision_node_additional_order import AdditionalOrderDecisionNode


def make_node(state="ORDER_CONFIRM"):
    node = AdditionalOrderDecisionNode.__new__(AdditionalOrderDecisionNode)
    node.state = state
    node.session_id = "session-1"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": 2,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def strawberry_addition(text="딸기스무디 두 잔도 추가해주세요."):
    return {
        "text": text,
        "intent": "ORDER",
        "confidence": 0.999,
        "needs_reprompt": False,
        "order_status": "VALID",
        "items": [
            {
                "item_id": 0,
                "menu": "딸기스무디",
                "temperature": "ICE",
                "quantity": 2,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "explicit_slots": {
            "menu": "딸기스무디",
            "menus": ["딸기스무디"],
            "temperature": None,
            "quantity": 2,
        },
    }


def strawberry_addition_without_quantity(
    text="딸기스무디도 추가해 주세요.",
):
    result = strawberry_addition(text)
    result["order_status"] = "INCOMPLETE"
    result["needs_reprompt"] = True
    result["items"][0]["quantity"] = None
    result["items"][0]["missing_slots"] = ["quantity"]
    result["explicit_slots"]["quantity"] = None
    return result


def test_live_strawberry_addition_is_appended_during_order_confirm():
    node = make_node()

    result = node.make_decision(strawberry_addition())

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "additional_order_appended"
    assert node.state == "ORDER_CONFIRM"
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in node.current_order["items"]
    ] == [
        ("아메리카노", "ICE", 2),
        ("딸기스무디", "ICE", 2),
    ]


def test_s5_one_cup_addition_preserves_existing_order():
    node = make_node()
    node.current_order["items"][0]["quantity"] = 1
    addition = strawberry_addition("딸기스무디 한 잔도 추가해 주세요.")
    addition["items"][0]["quantity"] = 1
    addition["explicit_slots"]["quantity"] = 1

    result = node.make_decision(addition)

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "additional_order_appended"
    assert node.state == "ORDER_CONFIRM"
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in node.current_order["items"]
    ] == [
        ("아메리카노", "ICE", 1),
        ("딸기스무디", "ICE", 1),
    ]


def test_missing_slot_on_added_drink_targets_new_item_not_existing_item():
    node = make_node()

    result = node.make_decision(strawberry_addition_without_quantity())

    assert result["decision"] == "ASK_QUANTITY"
    assert result["reason"] == "missing_quantity"
    assert result["missing_item_id"] == 1
    assert result["response_args"]["menu"] == "딸기스무디"
    assert [item["item_id"] for item in node.current_order["items"]] == [0, 1]
    assert node.current_order["items"][0]["quantity"] == 2
    assert node.current_order["items"][1]["quantity"] is None


def test_natural_more_please_variant_is_also_appended():
    node = make_node()

    result = node.make_decision(
        strawberry_addition("딸기스무디 두 잔 더 주세요.")
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert len(node.current_order["items"]) == 2
    assert node.current_order["items"][1]["menu"] == "딸기스무디"
    assert node.current_order["items"][1]["quantity"] == 2


def test_finish_prompt_can_accept_a_slot_bearing_additional_drink():
    node = make_node(state="WAIT_NEXT_CUSTOMER")

    result = node.make_decision(strawberry_addition())

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "additional_order_appended"
    assert node.state == "ORDER_CONFIRM"
    assert [item["item_id"] for item in node.current_order["items"]] == [0, 1]
    assert [item["menu"] for item in node.current_order["items"]] == [
        "아메리카노",
        "딸기스무디",
    ]


def test_finish_prompt_missing_slot_is_asked_for_the_added_drink():
    node = make_node(state="WAIT_NEXT_CUSTOMER")

    result = node.make_decision(strawberry_addition_without_quantity())

    assert result["decision"] == "ASK_QUANTITY"
    assert result["missing_item_id"] == 1
    assert result["response_args"]["menu"] == "딸기스무디"
    assert node.current_order["items"][0]["quantity"] == 2


def test_explicit_addition_cue_can_override_a_modify_model_prediction():
    node = make_node()
    addition = strawberry_addition("딸기스무디 한 잔도 추가해 주세요.")
    addition["intent"] = "MODIFY"
    addition["confidence"] = 0.688
    addition["items"][0]["quantity"] = 1
    addition["explicit_slots"]["quantity"] = 1

    result = node.make_decision(addition)

    assert result["decision"] == "CONFIRM_ORDER"
    assert [item["menu"] for item in node.current_order["items"]] == [
        "아메리카노",
        "딸기스무디",
    ]


def test_plain_menu_mention_without_addition_cue_still_cannot_mutate_confirmation():
    node = make_node()
    result_input = strawberry_addition("딸기스무디 두 잔 주세요.")

    result = node.make_decision(result_input)

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "confirmation_required"
    assert len(node.current_order["items"]) == 1
    assert node.current_order["items"][0]["menu"] == "아메리카노"
