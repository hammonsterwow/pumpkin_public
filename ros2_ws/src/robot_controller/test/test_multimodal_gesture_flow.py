from __future__ import annotations

from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.head_motion_node import normalize_head_command


def make_node(state="ORDER_CONFIRM", current_order=None):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "session-gesture-test"
    node.current_order = current_order
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.human_presence_initialized = True
    node.last_human_presence = True
    node._customer_exit_seen = False
    return node


def order():
    return {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": 1,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
    }


def nlu(text):
    return {
        "text": text,
        "intent": "UNKNOWN",
        "confidence": 0.0,
        "needs_reprompt": True,
        "order_status": "NONE",
        "items": [],
    }


def assert_same_dialogue_result(spoken, visual):
    for key in ("decision", "response_key", "state", "next_state"):
        assert visual.get(key) == spoken.get(key)


def test_spoken_yes_and_user_nod_share_affirm_path_in_order_confirm():
    spoken_node = make_node(current_order=order())
    visual_node = make_node(current_order=order())

    spoken = spoken_node.make_decision(nlu("네"))
    visual = visual_node.make_user_gesture_decision("NOD")

    assert visual is not None
    assert_same_dialogue_result(spoken, visual)
    assert spoken_node.state == visual_node.state == "WAIT_NEXT_CUSTOMER"
    assert visual["input_modality"] == "VISION_GESTURE"
    assert visual["user_gesture"] == "NOD"


def test_spoken_no_and_user_shake_share_deny_path_in_order_confirm():
    spoken_node = make_node(current_order=order())
    visual_node = make_node(current_order=order())

    spoken = spoken_node.make_decision(nlu("아니요"))
    visual = visual_node.make_user_gesture_decision("SHAKE")

    assert visual is not None
    assert_same_dialogue_result(spoken, visual)
    assert spoken_node.state == visual_node.state
    assert visual["input_modality"] == "VISION_GESTURE"
    assert visual["user_gesture"] == "SHAKE"


def test_user_gesture_is_ignored_outside_confirmation_states():
    node = make_node(state="ORDER_LISTEN", current_order=order())

    assert node.make_user_gesture_decision("NOD") is None
    assert node.make_user_gesture_decision("SHAKE") is None


def test_finish_prompt_accepts_visual_yes_and_no():
    yes_node = make_node(state="WAIT_NEXT_CUSTOMER", current_order=order())
    no_node = make_node(state="WAIT_NEXT_CUSTOMER", current_order=order())

    yes = yes_node.make_user_gesture_decision("NOD")
    no = no_node.make_user_gesture_decision("SHAKE")

    assert yes is not None and yes["decision"] == "NEXT_CUSTOMER_READY"
    assert yes_node.state == "WAIT_CUSTOMER_EXIT"
    assert yes["next_state"] == "WAIT_CUSTOMER_EXIT"
    assert yes_node._customer_exit_seen is False
    assert no is not None and no["decision"] == "CONTINUE_ORDER"
    assert no_node.state == "ORDER_LISTEN"


def test_robot_head_action_contract_maps_to_motor_commands():
    assert normalize_head_command("NOD") == "NOD"
    assert normalize_head_command("DOUBLE_NOD") == "DOUBLE_NOD"
    assert normalize_head_command("SHAKE") == "SHAKE"
    assert normalize_head_command("TURN_LEFT") == "TURN_LEFT"
    assert normalize_head_command("TURN_RIGHT") == "TURN_RIGHT"
    assert normalize_head_command("CENTER") == "CENTER"


def test_legacy_look_actions_fall_back_to_center():
    assert normalize_head_command("LOOK_FORWARD") == "CENTER"
    assert normalize_head_command("LOOK_USER") == "CENTER"
    assert normalize_head_command("LOOK_SCREEN") == "CENTER"
    assert normalize_head_command("UNKNOWN") is None
