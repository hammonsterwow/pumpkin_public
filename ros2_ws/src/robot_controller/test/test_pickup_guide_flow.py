from robot_controller.action_node import ActionNode
from robot_controller.response_manager_pickup import PickupAwareResponseManager


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


def test_drink_pickup_is_opposite_default_restroom(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)

    response = PickupAwareResponseManager().render(
        guide_decision("음료수 어디서 받아요?")
    )
    action = ActionNode.__new__(ActionNode).make_action(response)

    assert response["response_args"]["target"] == "PICKUP"
    assert response["response_args"]["direction"] == "LEFT"
    assert response["speech"] == (
        "음료 수령대는 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
    )
    assert response["display_text"] == "음료 수령대 ← 왼쪽"
    assert action["head"] == "TURN_LEFT"
    assert action["arm"] == "POINT_LEFT"
    assert action["display"] == "GUIDE_LEFT"


def test_pickup_flips_when_restroom_direction_flips(monkeypatch):
    monkeypatch.setenv("PUMPKIN_RESTROOM_DIRECTION", "LEFT")

    response = PickupAwareResponseManager().render(
        guide_decision("주문한 음료는 어디서 받아요?")
    )
    action = ActionNode.__new__(ActionNode).make_action(response)

    assert response["response_args"]["target"] == "PICKUP"
    assert response["response_args"]["direction"] == "RIGHT"
    assert response["speech"] == (
        "음료 수령대는 오른쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
    )
    assert response["display_text"] == "음료 수령대 → 오른쪽"
    assert action["head"] == "TURN_RIGHT"
    assert action["arm"] == "POINT_RIGHT"


def test_pickup_synonyms_are_detected(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)
    manager = PickupAwareResponseManager()

    for text in (
        "음료 어디서 받아요?",
        "음료 받는 곳이 어디예요?",
        "음료 수령대가 어디예요?",
        "픽업 어디예요?",
        "픽업대가 어디예요?",
        "음료 수령은 어디서 해요?",
        "커피 어디서 찾아요?",
    ):
        response = manager.render(guide_decision(text))
        assert response["response_args"]["target"] == "PICKUP"
        assert response["response_args"]["direction"] == "LEFT"
        assert response["speech"] == (
            "음료 수령대는 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
        )


def test_fuzzy_pickup_asr_variants_are_recovered_only_with_location_context(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)
    manager = PickupAwareResponseManager()

    # Representative live Whisper distortions of 픽업 / 픽업대.
    for text in (
        "피껌 어디서예요?",
        "피업데이 어디 있어요?",
        "피 업데이 위치가 어디예요?",
        "피컵대가 어디예요?",
    ):
        response = manager.render(guide_decision(text))
        assert response["response_args"]["target"] == "PICKUP"
        assert response["response_args"]["direction"] == "LEFT"
        assert response["speech"] == (
            "음료 수령대는 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
        )


def test_fuzzy_pickup_does_not_trigger_from_unrelated_guide_text(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)
    manager = PickupAwareResponseManager()

    for text in (
        "매장 위치가 어디예요?",
        "화장실이 어디예요?",
        "피곤해요 어디 앉아도 돼요?",
        "매장 이용 안내해 주세요",
    ):
        response = manager.render(guide_decision(text))
        assert response["response_args"].get("target") != "PICKUP"


def test_generic_store_guide_is_not_mistaken_for_pickup(monkeypatch):
    monkeypatch.delenv("PUMPKIN_RESTROOM_DIRECTION", raising=False)

    response = PickupAwareResponseManager().render(
        guide_decision("매장 이용 안내해 주세요")
    )

    assert response["response_args"].get("target") is None
    assert response["response_args"].get("direction") is None
    assert response["speech"] == "매장 이용 안내를 도와드릴게요."
