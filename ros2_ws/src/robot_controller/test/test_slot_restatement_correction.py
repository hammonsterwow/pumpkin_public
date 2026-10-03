from robot_controller.decision_node import DecisionNode
from robot_controller.dialogue_slots import extract_explicit_slots


def make_waiting_temperature_node():
    node = DecisionNode.__new__(DecisionNode)
    node.state = "ASK_TEMPERATURE"
    node.session_id = "test-session"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": None,
                "quantity": 1,
                "missing_slots": ["temperature"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
    }
    node.waiting_for = {"item_id": 0, "slot": "temperature"}
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def nlu_result(text):
    slots = extract_explicit_slots(text)
    return {
        "text": text,
        "intent": "ORDER",
        "confidence": 0.999,
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        # The live NLU node attaches explicit_slots and DecisionNode prefers
        # those literal values while a slot question is active.
        "items": [],
        "explicit_slots": slots,
    }


def assert_strawberry_twenty(decision):
    assert decision["decision"] == "CONFIRM_ORDER"
    item = decision["order"]["items"][0]
    assert item["menu"] == "딸기스무디"
    assert item["temperature"] == "ICE"
    assert item["quantity"] == 20


def test_anira_phrase_grounds_requested_target_not_source():
    slots = extract_explicit_slots(
        "아메리카노가 아니라 딸기스무디 스무 잔 주세요."
    )

    assert slots["menu"] == "딸기스무디"
    assert slots["menus"] == ["딸기스무디"]
    assert slots["quantity"] == 20
    assert slots["correction"] == {
        "slot": "menu",
        "from": "아메리카노",
        "to": "딸기스무디",
    }


def test_direct_full_restatement_replaces_stale_menu_while_waiting_temperature():
    node = make_waiting_temperature_node()

    decision = node.make_decision(nlu_result("딸기스무디 스무 잔 주세요."))

    assert_strawberry_twenty(decision)


def test_hallucinated_source_in_correction_still_uses_requested_strawberry_target():
    node = make_waiting_temperature_node()

    decision = node.make_decision(
        nlu_result("아메리카노가 아니라 딸기스무디 스무 잔 주세요.")
    )

    assert_strawberry_twenty(decision)


def test_malgo_menu_restatement_does_not_attach_strawberry_ice_to_americano():
    node = make_waiting_temperature_node()

    decision = node.make_decision(
        nlu_result("아메리카노 말고 딸기스무디 주세요.")
    )

    assert decision["decision"] == "CONFIRM_ORDER"
    item = decision["order"]["items"][0]
    assert item["menu"] == "딸기스무디"
    assert item["temperature"] == "ICE"
    assert item["quantity"] == 1
