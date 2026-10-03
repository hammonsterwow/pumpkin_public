from robot_controller.decision_node import DecisionNode
from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.dialogue_slots import extract_explicit_slots


def make_decision_node():
    node = DecisionNode.__new__(DecisionNode)
    node.state = "ORDER_CONFIRM"
    node.session_id = "test-session"
    node.current_order = None
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def complete_item(item_id, menu, temperature="ICE", quantity=1):
    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": [],
        "validation_errors": [],
    }


def nlu_result(text):
    slots = extract_explicit_slots(text)
    item = {
        "item_id": 0,
        "menu": slots.get("menu"),
        "temperature": slots.get("temperature"),
        "quantity": slots.get("quantity"),
    }
    return {
        "text": text,
        "intent": "ORDER",
        "confidence": 0.99,
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        "items": [item],
        "explicit_slots": slots,
    }


def test_vanilla_latte_stt_spelling_is_not_cafe_latte():
    slots = extract_explicit_slots("바닐라떼 세 잔 주세요")

    assert slots["menu"] == "바닐라라떼"
    assert slots["menus"] == ["바닐라라떼"]
    assert slots["quantity"] == 3


def test_menu_correction_keeps_from_and_to_direction():
    slots = extract_explicit_slots("아메리카노를 딸기스무디로 바꿀게요")

    assert slots["menu"] == "딸기스무디"
    assert slots["menus"] == ["딸기스무디"]
    assert slots["correction"] == {
        "slot": "menu",
        "from": "아메리카노",
        "to": "딸기스무디",
    }


def test_quantity_correction_keeps_from_and_to_direction():
    slots = extract_explicit_slots("세 잔 말고 다섯 잔 주세요")

    assert slots["quantity"] == 5
    assert slots["correction"] == {
        "slot": "quantity",
        "from": 3,
        "to": 5,
    }


def test_single_quantity_correction_uses_requested_target():
    slots = extract_explicit_slots("다섯 잔으로 바꿔줘")

    assert slots["quantity"] == 5
    assert slots["correction"] == {
        "slot": "quantity",
        "from": None,
        "to": 5,
    }


def test_noisy_short_denial_is_accepted_during_confirmation():
    resolver = DialogueActResolver()

    assert resolver.resolve_confirmation(
        {"text": "아니요? 야호!"},
        state="ORDER_CONFIRM",
        confirmation_states={"ORDER_CONFIRM"},
    ) == "DENY"
    assert resolver.resolve_confirmation(
        {"text": "네, 맞아요!"},
        state="ORDER_CONFIRM",
        confirmation_states={"ORDER_CONFIRM"},
    ) == "AFFIRM"


def test_single_item_can_be_corrected_without_saying_no_first():
    node = make_decision_node()
    node.current_order = {
        "items": [complete_item(0, "카페라떼", temperature="ICE", quantity=3)],
        "order_status": "VALID",
    }

    decision = node.make_decision(nlu_result("카페라떼 말고 바닐라떼요"))

    assert decision["decision"] == "CONFIRM_ORDER"
    assert decision["reason"] == "order_corrected"
    assert decision["order"]["items"][0]["menu"] == "바닐라라떼"
    assert decision["order"]["items"][0]["temperature"] == "ICE"
    assert decision["order"]["items"][0]["quantity"] == 3


def test_quantity_can_be_corrected_directly_during_confirmation():
    node = make_decision_node()
    node.current_order = {
        "items": [complete_item(0, "카페라떼", temperature="ICE", quantity=3)],
        "order_status": "VALID",
    }

    decision = node.make_decision(nlu_result("두 잔으로 바꿔줘"))

    assert decision["decision"] == "CONFIRM_ORDER"
    assert decision["order"]["items"][0]["menu"] == "카페라떼"
    assert decision["order"]["items"][0]["quantity"] == 2


def test_from_to_quantity_correction_uses_last_quantity():
    node = make_decision_node()
    node.current_order = {
        "items": [complete_item(0, "레몬에이드", temperature="ICE", quantity=3)],
        "order_status": "VALID",
    }

    decision = node.make_decision(nlu_result("세 잔 말고 다섯 잔 주세요"))

    assert decision["decision"] == "CONFIRM_ORDER"
    assert decision["order"]["items"][0]["menu"] == "레몬에이드"
    assert decision["order"]["items"][0]["quantity"] == 5


def test_multi_item_from_to_correction_changes_only_named_source():
    node = make_decision_node()
    node.current_order = {
        "items": [
            complete_item(0, "아메리카노", temperature="ICE", quantity=1),
            complete_item(1, "카페라떼", temperature="HOT", quantity=2),
        ],
        "order_status": "VALID",
    }

    decision = node.make_decision(
        nlu_result("아메리카노를 딸기스무디로 바꿀게요")
    )

    assert decision["decision"] == "CONFIRM_ORDER"
    assert [item["menu"] for item in decision["order"]["items"]] == [
        "딸기스무디",
        "카페라떼",
    ]
    assert decision["order"]["items"][1]["temperature"] == "HOT"
    assert decision["order"]["items"][1]["quantity"] == 2
