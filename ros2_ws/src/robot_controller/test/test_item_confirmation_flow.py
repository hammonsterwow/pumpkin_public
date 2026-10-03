from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.order_dialogue_manager import OrderDialogueManager


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


def ice_americano_without_quantity():
    return {
        "schema_version": "1.0",
        "model_name": "structure_b_item_query_decoder",
        "text": "아이스 아메리카노 주세요",
        "intent": "ORDER",
        "intent_confidence": 1.0,
        "confidence": 1.0,
        "order_status": "INCOMPLETE",
        "order_status_confidence": 1.0,
        "needs_reprompt": True,
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
            }
        ],
        "explicit_slots": {
            "menu": "아메리카노",
            "menus": ["아메리카노"],
            "temperature": "ICE",
            "quantity": None,
        },
    }


def two_cold_drinks_without_quantity():
    return {
        "schema_version": "1.0",
        "model_name": "structure_b_item_query_decoder",
        "text": "딸기 스무디랑 레몬 에이드 주문할게요",
        "intent": "ORDER",
        "intent_confidence": 1.0,
        "confidence": 1.0,
        "order_status": "INCOMPLETE",
        "order_status_confidence": 1.0,
        "needs_reprompt": True,
        "items": [
            {
                "item_id": 0,
                "menu": "딸기스무디",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
            },
            {
                "item_id": 1,
                "menu": "레몬에이드",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
            },
        ],
        "explicit_slots": {
            "menu": "딸기스무디",
            "menus": ["딸기스무디", "레몬에이드"],
            "temperature": None,
            "quantity": None,
        },
    }


def short_answer(text):
    return {
        "text": text,
        "intent": "ORDER",
        "intent_confidence": 1.0,
        "confidence": 1.0,
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        "items": [],
    }


def quantity_answer(quantity):
    return {
        "text": f"{quantity}잔",
        "intent": "ORDER",
        "intent_confidence": 1.0,
        "confidence": 1.0,
        "order_status": "INCOMPLETE",
        "needs_reprompt": True,
        "items": [
            {
                "item_id": 0,
                "menu": None,
                "temperature": None,
                "quantity": quantity,
                "missing_slots": ["menu", "temperature"],
            }
        ],
        "explicit_slots": {
            "menu": None,
            "menus": [],
            "temperature": None,
            "quantity": quantity,
        },
    }


def enter_item_confirm(node):
    decision = node.make_decision(ice_americano_without_quantity())
    assert decision["decision"] == "CONFIRM_ITEM"
    assert decision["response_key"] == "confirm_item"
    assert node.state == "ITEM_CONFIRM"
    assert node.waiting_for == {"item_id": 0, "slot": "quantity"}
    return decision


def test_spoken_affirm_moves_from_item_confirmation_to_quantity():
    node = make_node()
    enter_item_confirm(node)

    decision = node.make_decision(short_answer("네"))

    assert decision["decision"] == "ASK_QUANTITY"
    assert decision["response_key"] == "ask_quantity"
    assert decision["reason"] == "item_confirmed"
    assert node.state == "ASK_QUANTITY"
    assert node.current_order["items"][0]["menu"] == "아메리카노"
    assert node.current_order["items"][0]["temperature"] == "ICE"
    assert node.current_order["items"][0]["quantity"] is None


def test_spoken_deny_discards_tentative_item_and_asks_order_again():
    node = make_node()
    enter_item_confirm(node)

    decision = node.make_decision(short_answer("아니요"))

    assert decision["decision"] == "REORDER_REQUEST"
    assert decision["response_key"] == "ask_order"
    assert decision["reason"] == "item_confirmation_denied"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is None
    assert node.waiting_for is None


def test_visual_nod_matches_spoken_affirm_at_item_confirmation():
    node = make_node()
    enter_item_confirm(node)

    decision = node.make_user_gesture_decision("NOD")

    assert decision["decision"] == "ASK_QUANTITY"
    assert decision["response_key"] == "ask_quantity"
    assert decision["input_modality"] == "VISION_GESTURE"
    assert decision["user_gesture"] == "NOD"


def test_visual_shake_matches_spoken_deny_at_item_confirmation():
    node = make_node()
    enter_item_confirm(node)

    decision = node.make_user_gesture_decision("SHAKE")

    assert decision["decision"] == "REORDER_REQUEST"
    assert decision["response_key"] == "ask_order"
    assert decision["input_modality"] == "VISION_GESTURE"
    assert decision["user_gesture"] == "SHAKE"


def test_multi_item_order_collects_each_missing_quantity_without_single_item_confirm():
    node = make_node()

    first = node.make_decision(two_cold_drinks_without_quantity())

    assert first["decision"] == "ASK_QUANTITY"
    assert first["response_key"] == "ask_quantity"
    assert first["response_args"]["menu"] == "딸기스무디"
    assert node.state == "ASK_QUANTITY"
    assert node.waiting_for == {"item_id": 0, "slot": "quantity"}
    assert len(node.current_order["items"]) == 2

    second = node.make_decision(quantity_answer(2))

    assert second["decision"] == "ASK_QUANTITY"
    assert second["response_key"] == "ask_quantity"
    assert second["response_args"]["menu"] == "레몬에이드"
    assert node.state == "ASK_QUANTITY"
    assert node.waiting_for == {"item_id": 1, "slot": "quantity"}
    assert node.current_order["items"][0]["quantity"] == 2
    assert node.current_order["items"][1]["quantity"] is None

    final = node.make_decision(quantity_answer(1))

    assert final["decision"] == "CONFIRM_ORDER"
    assert final["response_key"] == "confirm_order"
    assert node.state == "ORDER_CONFIRM"
    assert [
        (item["menu"], item["temperature"], item["quantity"])
        for item in node.current_order["items"]
    ] == [
        ("딸기스무디", "ICE", 2),
        ("레몬에이드", "ICE", 1),
    ]

def test_live_three_cup_asr_artifacts_are_recovered_only_in_quantity_state():
    observed_transcripts = (
        "세전! 세전이요.",
        "새해 쟌",
        "세. 잠.",
        "새 잔",
        "체점",
        "3단",
    )

    for transcript in observed_transcripts:
        node = make_node()
        enter_item_confirm(node)
        ask_quantity = node.make_decision(short_answer("네"))
        assert ask_quantity["decision"] == "ASK_QUANTITY"

        decision = node.make_decision(short_answer(transcript))

        assert decision["decision"] == "CONFIRM_ORDER"
        assert node.current_order["items"][0]["quantity"] == 3
        assert decision["nlu_result"]["contextual_slot_recovery"] == {
            "slot": "quantity",
            "quantity": 3,
            "source_text": transcript,
        }


def test_live_quantity_artifact_is_not_recovered_outside_quantity_state():
    node = make_node()
    original = short_answer("체점")

    assert node.recover_contextual_slot_answer(original) is original
    assert "explicit_slots" not in original

