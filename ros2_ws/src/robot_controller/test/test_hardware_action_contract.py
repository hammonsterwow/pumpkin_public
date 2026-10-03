from robot_controller.action_node import ActionNode
from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.face_display_node import normalize_face_name


def test_base_hardware_action_rules_are_preserved():
    node = ActionNode.__new__(ActionNode)

    confirm = node.get_action_rule({"decision": "CONFIRM_ORDER"})
    assert confirm == {
        "face": "SMILE",
        "display": "ORDER_CONFIRM",
        "head": "CENTER",
        "arm": "WAIT",
        "priority": "NORMAL",
    }

    completed = node.get_action_rule({"decision": "ORDER_CONFIRMED"})
    assert completed == {
        "face": "HAPPY",
        "display": "ORDER_ACCEPTED",
        "head": "DOUBLE_NOD",
        "arm": "WAIT",
        "priority": "NORMAL",
    }

    payment = node.get_action_rule({"decision": "PAYMENT_GUIDE"})
    assert payment == {
        "face": "SMILE",
        "display": "PAYMENT_GUIDE",
        "head": "CENTER",
        "arm": "POINT_DISPLAY",
        "priority": "NORMAL",
    }


def test_error_hardware_actions_use_error_face():
    node = ActionNode.__new__(ActionNode)

    assert node.make_error_action("boom")["face"] == "ERROR"
    assert node.get_action_rule({"decision": "RESPONSE_ERROR"})["face"] == "ERROR"
    assert node.get_action_rule({"decision": "STT_FAILED"})["face"] == "ERROR"


def test_face_display_contract_accepts_all_firmware_faces():
    for face in ["NEUTRAL", "SMILE", "HAPPY", "QUESTION", "ERROR"]:
        assert normalize_face_name(face.lower()) == face


def test_order_handoff_hardware_actions_are_preserved():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)

    continue_order = node.get_action_rule({"decision": "CONTINUE_ORDER"})
    assert continue_order == {
        "face": "QUESTION",
        "display": "ORDER_LISTEN",
        "head": "CENTER",
        "arm": "WAIT",
        "priority": "NORMAL",
    }

    next_customer = node.get_action_rule({"decision": "NEXT_CUSTOMER_READY"})
    assert next_customer == {
        "face": "NEUTRAL",
        "display": "IDLE",
        "head": "CENTER",
        "arm": "GOODBYE_WAVE",
        "priority": "NORMAL",
    }

    assert "ORDER_CONFIRMED" in node.LISTEN_AFTER_TTS_DECISIONS
    assert "CONTINUE_ORDER" in node.LISTEN_AFTER_TTS_DECISIONS
    assert "NEXT_CUSTOMER_READY" not in node.LISTEN_AFTER_TTS_DECISIONS

def test_arm_gestures_are_bound_only_to_the_intended_situations():
    base = ActionNode.__new__(ActionNode)
    handoff = OrderHandoffActionNode.__new__(OrderHandoffActionNode)

    assert base.get_action_rule({"decision": "START_ORDER"})["arm"] == "WAIT"
    retry = base.get_action_rule({"decision": "STT_RETRY"})
    assert retry["head"] == "SHAKE"
    assert retry["arm"] == "UNSURE"
    assert base.get_action_rule({"decision": "ORDER_CONFIRMED"})["arm"] == "WAIT"
    assert handoff.get_action_rule(
        {"decision": "NEXT_CUSTOMER_READY"}
    )["arm"] == "GOODBYE_WAVE"

