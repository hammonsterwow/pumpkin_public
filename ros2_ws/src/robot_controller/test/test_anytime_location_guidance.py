import pytest

from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.decision_node import DecisionNode
from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.response_manager_pickup import PickupAwareResponseManager


def make_active_node(state):
    node = DecisionNode.__new__(DecisionNode)
    node.state = state
    node.session_id = "test-session"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "quantity": None,
                "temperature": "ICE",
            }
        ]
    }
    node.waiting_for = {"item_id": 0, "slot": "quantity"}
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


@pytest.mark.parametrize(
    "state",
    [
        "ASK_MENU",
        "ASK_QUANTITY",
        "ASK_TEMPERATURE",
        "ORDER_CONFIRM",
        "ORDER_CORRECTION",
    ],
)
@pytest.mark.parametrize(
    "text",
    [
        "화장실 어디예요?",
        "픽업대가 어디예요?",
    ],
)
def test_location_guide_interrupts_any_active_order_state_without_losing_context(
    state,
    text,
):
    node = make_active_node(state)
    original_order = node.current_order
    original_waiting = node.waiting_for

    decision = node.make_decision(
        {
            "text": text,
            "intent": "GUIDE",
            "confidence": 0.99,
            "needs_reprompt": False,
            "items": [],
        }
    )

    assert decision["decision"] == "GUIDE_CUSTOMER"
    assert decision["response_key"] == "guide_customer"
    assert decision["reason"] == "guide_detected_during_order"
    assert decision["state"] == state

    # Guidance is a temporary side request. The next user turn must continue the
    # exact order and pending-slot question that were active before the guide.
    assert node.state == state
    assert node.current_order is original_order
    assert node.waiting_for is original_waiting


@pytest.mark.parametrize(
    ("state", "resume_decision", "resume_text"),
    [
        ("ORDER_CONFIRM", "CONFIRM_ORDER", "맞으신가요?"),
        ("WAIT_NEXT_CUSTOMER", "ORDER_CONFIRMED", "주문을 마치시겠어요?"),
    ],
)
def test_guide_resumes_guarded_confirmation_prompt(
    state,
    resume_decision,
    resume_text,
):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "test-session"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "quantity": 1,
                "temperature": "ICE",
            }
        ]
    }
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2

    decision = node.make_decision(
        {
            "text": "픽업대가 어디예요?",
            "intent": "GUIDE",
            "confidence": 0.99,
            "needs_reprompt": False,
            "items": [],
        }
    )

    assert decision["decision"] == "GUIDE_CUSTOMER"
    assert decision["state"] == state
    assert decision["resume_prompt"]["decision"] == resume_decision

    response = PickupAwareResponseManager().render(decision)
    assert "음료 수령대는" in response["speech"]
    assert resume_text in response["speech"]

    assert (
        OrderHandoffActionNode.resolve_stt_trigger_mode(resume_decision)
        == "confirm"
    )
