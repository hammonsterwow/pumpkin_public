from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.dialogue_slots import extract_explicit_slots
from robot_controller.nlu_postprocess import reconcile_explicit_order_evidence
from robot_controller.order_dialogue_manager import OrderDialogueManager
from robot_controller.order_schema import extract_items


def make_node():
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = "ORDER_LISTEN"
    node.session_id = "test-session"
    node.current_order = None
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.dialogue_act_resolver = DialogueActResolver()
    node.order_manager = OrderDialogueManager(
        slot_priority=node.SLOT_PRIORITY,
        group_shared_slots=node.GROUP_SHARED_SLOTS,
    )
    return node


def literal_nlu(text):
    slots = extract_explicit_slots(text)
    result = {
        "text": text,
        "intent": "ORDER",
        "confidence": 0.99,
        "intent_confidence": 0.99,
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        "items": [],
        "explicit_slots": slots,
    }
    return result


def test_live_partial_order_recovers_instead_of_losing_first_item():
    node = make_node()
    text = "한 잔이랑 바닐라라떼 15 잔."
    slots = extract_explicit_slots(text)
    first = {
        "text": text,
        "intent": "ORDER",
        "confidence": 0.99,
        "intent_confidence": 0.99,
        "order_status": "VALID",
        "needs_reprompt": False,
        "items": [
            {"item_id": 0, "menu": "아메리카노", "temperature": "ICE", "quantity": 1},
            {"item_id": 1, "menu": "바닐라라떼", "temperature": "HOT", "quantity": 1},
        ],
        "explicit_slots": slots,
    }
    reconcile_explicit_order_evidence(first, slots)

    decision = node.make_decision(first)

    assert decision["decision"] == "ASK_MENU"
    assert decision["waiting_for"] == {"item_id": 0, "slot": "menu"}
    assert decision["order"]["items"][0]["quantity"] == 1
    assert decision["order"]["items"][1]["menu"] == "바닐라라떼"
    assert decision["order"]["items"][1]["quantity"] == 15

    strawberry = literal_nlu("딸기스무디 주세요.")
    strawberry["items"] = extract_items({"items": [strawberry["explicit_slots"]]})
    decision = node.make_decision(strawberry)

    assert decision["decision"] == "ASK_TEMPERATURE"
    assert decision["waiting_for"] == {"item_id": 1, "slot": "temperature"}
    assert decision["order"]["items"][0]["menu"] == "딸기스무디"
    assert decision["order"]["items"][0]["temperature"] == "ICE"
    assert decision["order"]["items"][0]["quantity"] == 1

    hot = literal_nlu("하세요로.")
    hot["items"] = extract_items({"items": [hot["explicit_slots"]]})
    decision = node.make_decision(hot)

    assert decision["decision"] == "CONFIRM_ORDER"
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in decision["order"]["items"]
    ] == [
        ("딸기스무디", "ICE", 1),
        ("바닐라라떼", "HOT", 15),
    ]
