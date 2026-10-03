from robot_controller.decision_node_additional_order import AdditionalOrderDecisionNode
from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.dialogue_slots import extract_explicit_slots, has_explicit_slots
from robot_controller.order_dialogue_manager import OrderDialogueManager
from robot_controller.order_schema import extract_items
from robot_controller.response_manager import ResponseManager


def complete_item(item_id, menu, temperature, quantity):
    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": [],
        "validation_errors": [],
    }


def make_node(items):
    node = AdditionalOrderDecisionNode.__new__(AdditionalOrderDecisionNode)
    node.state = "ORDER_CONFIRM"
    node.session_id = "test-session"
    node.current_order = {
        "schema_version": "1.0",
        "session_id": "test-session",
        "intent": "ORDER",
        "confidence": 0.99,
        "items": [dict(item) for item in items],
        "order_status": "VALID",
        "needs_reprompt": False,
        "waiting_for": None,
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.correction_target_item_id = None
    node.dialogue_act_resolver = DialogueActResolver()
    node.order_manager = OrderDialogueManager(
        slot_priority=node.SLOT_PRIORITY,
        group_shared_slots=node.GROUP_SHARED_SLOTS,
    )
    return node


def nlu_result(text, *, intent="ORDER"):
    slots = extract_explicit_slots(text)
    items = (
        extract_items({"items": [slots]})
        if has_explicit_slots(slots)
        else []
    )
    return {
        "text": text,
        "intent": intent,
        "intent_confidence": 0.999,
        "confidence": 0.999,
        "order_status": "INCOMPLETE" if items else "NONE",
        "needs_reprompt": bool(items),
        "items": items,
        "explicit_slots": slots,
    }


def test_staged_partial_replacement_keeps_other_menu_unchanged():
    node = make_node(
        [
            complete_item(0, "아메리카노", "ICE", 2),
            complete_item(1, "카페라떼", "HOT", 1),
        ]
    )
    response_manager = ResponseManager()

    start = node.make_decision(nlu_result("수정할게요", intent="MODIFY"))
    assert start["decision"] == "MODIFY_ORDER"
    assert start["response_key"] == "ask_correction_target_selection"
    assert node.state == node.CORRECTION_TARGET_STATE
    assert response_manager.render_speech(start["response_key"], start) == (
        "어떤 음료를 바꿀까요?"
    )

    target = node.make_decision(nlu_result("아이스 아메리카노 두 잔"))
    assert target["decision"] == "MODIFY_ORDER"
    assert target["response_key"] == "ask_correction_replacement"
    assert node.state == node.CORRECTION_REPLACEMENT_STATE
    assert node.correction_target_item_id == 0
    assert response_manager.render_speech(target["response_key"], target) == (
        "아이스 아메리카노 2잔을 어떤 메뉴로 변경할까요?"
    )

    replaced = node.make_decision(nlu_result("레몬에이드 다섯 잔"))
    assert replaced["decision"] == "CONFIRM_ORDER"
    assert replaced["reason"] == "order_corrected"
    assert replaced["order"]["items"] == [
        complete_item(0, "레몬에이드", "ICE", 5),
        complete_item(1, "카페라떼", "HOT", 1),
    ]
    assert response_manager.render_speech("confirm_order", replaced) == (
        "아이스 레몬에이드 5잔, 따뜻한 카페라떼 1잔 맞으신가요?"
    )


def test_ambiguous_same_menu_never_guesses_target():
    node = make_node(
        [
            complete_item(0, "아메리카노", "ICE", 2),
            complete_item(1, "아메리카노", "HOT", 1),
        ]
    )
    response_manager = ResponseManager()

    ambiguous = node.make_decision(
        nlu_result("아메리카노 바꿀게요", intent="MODIFY")
    )

    assert ambiguous["decision"] == "MODIFY_ORDER"
    assert ambiguous["response_key"] == "ask_correction_target_disambiguation"
    assert ambiguous["reason"] == "correction_target_ambiguous"
    assert node.state == node.CORRECTION_TARGET_STATE
    assert node.correction_target_item_id is None
    assert len(ambiguous["response_args"]["candidates"]) == 2
    assert response_manager.render_speech(
        ambiguous["response_key"],
        ambiguous,
    ) == (
        "어느 아메리카노를 변경할까요? "
        "아이스 2잔 또는 따뜻한 1잔 중에서 말씀해 주세요."
    )

    narrowed = node.make_decision(nlu_result("아이스 아메리카노 두 잔"))
    assert narrowed["response_key"] == "ask_correction_replacement"
    assert node.state == node.CORRECTION_REPLACEMENT_STATE
    assert node.correction_target_item_id == 0
    assert response_manager.render_speech(narrowed["response_key"], narrowed) == (
        "아이스 아메리카노 2잔을 어떤 메뉴로 변경할까요?"
    )


def test_target_not_found_does_not_mutate_existing_order():
    original_items = [
        complete_item(0, "아메리카노", "ICE", 2),
        complete_item(1, "카페라떼", "HOT", 1),
    ]
    node = make_node(original_items)
    node.state = node.CORRECTION_TARGET_STATE

    decision = node.make_decision(nlu_result("바닐라라떼 한 잔"))

    assert decision["response_key"] == "ask_correction_target_not_found"
    assert node.state == node.CORRECTION_TARGET_STATE
    assert node.correction_target_item_id is None
    assert node.current_order["items"] == original_items


def test_existing_one_shot_from_to_correction_still_bypasses_target_selection():
    node = make_node(
        [
            complete_item(0, "아메리카노", "ICE", 2),
            complete_item(1, "카페라떼", "HOT", 1),
        ]
    )

    decision = node.make_decision(
        nlu_result("아메리카노를 딸기스무디로 바꿀게요", intent="MODIFY")
    )

    assert decision["decision"] == "CONFIRM_ORDER"
    assert [item["menu"] for item in decision["order"]["items"]] == [
        "딸기스무디",
        "카페라떼",
    ]
    assert node.state == "ORDER_CONFIRM"
