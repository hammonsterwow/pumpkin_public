from robot_controller.action_node import ActionNode
from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.response_manager import ResponseManager


def guide_decision(text):
    return {
        "decision": "GUIDE_CUSTOMER",
        "response_key": "guide_customer",
        "response_args": {"direction": None},
        "reason": "guide_detected",
        "state": "ORDER_LISTEN",
        "nlu_result": {
            "text": text,
            "intent": "GUIDE",
            "confidence": 0.99,
            "items": [],
        },
    }


def test_restroom_guide_resolves_to_right_by_default(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)

    response = ResponseManager().render(guide_decision("화장실 어디예요?"))

    assert response["response_args"]["target"] == "RESTROOM"
    assert response["response_args"]["direction"] == "RIGHT"
    assert response["speech"] == (
        "화장실은 오른쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
    )
    assert response["display_text"] == "화장실 → 오른쪽"

    action = ActionNode.__new__(ActionNode).make_action(response)
    assert action["face"] == "SMILE"
    assert action["head"] == "TURN_RIGHT"
    assert action["arm"] == "POINT_RIGHT"
    assert action["display"] == "GUIDE_RIGHT"


def test_restroom_direction_can_be_flipped_without_code_change(monkeypatch):
    monkeypatch.setenv("PUMPKIN_RESTROOM_DIRECTION", "LEFT")

    response = ResponseManager().render(guide_decision("화장실이 어디에 있나요?"))
    action = ActionNode.__new__(ActionNode).make_action(response)

    assert response["response_args"]["direction"] == "LEFT"
    assert response["speech"] == (
        "화장실은 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
    )
    assert response["display_text"] == "화장실 ← 왼쪽"
    assert action["head"] == "TURN_LEFT"
    assert action["arm"] == "POINT_LEFT"


def test_non_restroom_guide_keeps_existing_generic_behavior(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)

    response = ResponseManager().render(guide_decision("매장 이용 안내해 주세요"))
    action = ActionNode.__new__(ActionNode).make_action(response)

    assert response["response_args"].get("target") is None
    assert response["response_args"].get("direction") is None
    assert response["speech"] == "매장 이용 안내를 도와드릴게요."
    assert action["head"] == "CENTER"
    assert action["arm"] == "POINT_DISPLAY"


def test_location_guide_reopens_microphone_after_tts():
    assert "GUIDE_CUSTOMER" in OrderHandoffActionNode.LISTEN_AFTER_TTS_DECISIONS
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("GUIDE_CUSTOMER") == "start"
