from __future__ import annotations

from types import SimpleNamespace

from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.decision_node_order_handoff import OrderHandoffDecisionNode
from robot_controller.response_manager import ResponseManager


def make_node(state="ORDER_CONFIRM", current_order=None):
    node = OrderHandoffDecisionNode.__new__(OrderHandoffDecisionNode)
    node.state = state
    node.session_id = "session-1"
    node.current_order = current_order
    node.waiting_for = None
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    return node


def nlu(
    text,
    *,
    intent="UNKNOWN",
    confidence=0.0,
    needs_reprompt=True,
    order_status="NONE",
    items=None,
    explicit_slots=None,
):
    result = {
        "text": text,
        "intent": intent,
        "confidence": confidence,
        "needs_reprompt": needs_reprompt,
        "order_status": order_status,
        "items": list(items or []),
    }
    if explicit_slots is not None:
        result["explicit_slots"] = dict(explicit_slots)
    return result


def order(menu="아메리카노", temperature="ICE", quantity=1):
    return {
        "items": [
            {
                "item_id": 0,
                "menu": menu,
                "temperature": temperature,
                "quantity": quantity,
                "missing_slots": [],
                "validation_errors": [],
            }
        ],
        "order_status": "VALID",
    }


def test_affirmed_summary_asks_whether_to_finish_and_keeps_order_editable():
    active_order = order()
    node = make_node(current_order=active_order)

    result = node.make_decision(nlu("넵"))

    assert result["decision"] == "ORDER_CONFIRMED"
    assert result["response_key"] == "ask_next_customer"
    assert result["semantic_response_key"] == "ask_finish_order"
    assert result["state"] == "WAIT_NEXT_CUSTOMER"
    assert result["semantic_state"] == "WAIT_ORDER_FINISH"
    assert node.state == "WAIT_NEXT_CUSTOMER"
    assert node.current_order is active_order

    response = ResponseManager().render(result)
    assert response["speech"] == "주문을 마치시겠어요?"


def test_yes_after_finish_prompt_resets_to_idle_for_next_customer():
    node = make_node(state="WAIT_NEXT_CUSTOMER", current_order=order())

    result = node.make_decision(nlu("네"))

    assert result["decision"] == "NEXT_CUSTOMER_READY"
    assert result["semantic_event"] == "ORDER_FINISHED"
    assert result["response_key"] == "next_customer_ready"
    assert result["state"] == "IDLE"
    assert node.state == "IDLE"
    assert node.current_order is None
    assert node.session_id != "session-1"

    response = ResponseManager().render(result)
    assert response["speech"] == "주문이 완료되었습니다. 감사합니다."


def test_no_after_finish_prompt_keeps_same_customer_and_existing_order():
    active_order = order(menu="카페라떼", temperature="HOT")
    node = make_node(state="WAIT_NEXT_CUSTOMER", current_order=active_order)

    result = node.make_decision(nlu("아니요"))

    assert result["decision"] == "CONTINUE_ORDER"
    assert result["response_key"] == "continue_order"
    assert result["state"] == "ORDER_LISTEN"
    assert node.state == "ORDER_LISTEN"
    assert node.session_id == "session-1"
    assert node.current_order is active_order

    response = ResponseManager().render(result)
    assert response["speech"] == "추가 주문을 말씀해 주세요."


def test_explicit_additional_order_request_from_summary_keeps_current_order():
    active_order = order()
    node = make_node(current_order=active_order)

    result = node.make_decision(nlu("하나 더 주문할게요"))

    assert result["decision"] == "CONTINUE_ORDER"
    assert result["response_key"] == "continue_order"
    assert result["state"] == "ORDER_LISTEN"
    assert node.state == "ORDER_LISTEN"
    assert node.current_order is active_order


def test_modify_quantity_directly_while_finish_prompt_is_active():
    node = make_node(
        state="WAIT_NEXT_CUSTOMER",
        current_order=order(menu="카페라떼", temperature="HOT", quantity=1),
    )

    result = node.make_decision(
        nlu(
            "2잔으로 바꿀래요",
            intent="MODIFY",
            confidence=0.99,
            needs_reprompt=False,
            order_status="INCOMPLETE",
            items=[
                {
                    "menu": "아메리카노",
                    "temperature": "HOT",
                    "quantity": 2,
                }
            ],
            explicit_slots={
                "menu": None,
                "temperature": None,
                "quantity": 2,
            },
        )
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert result["reason"] == "order_corrected"
    assert node.state == "ORDER_CONFIRM"
    assert node.current_order["items"][0]["menu"] == "카페라떼"
    assert node.current_order["items"][0]["temperature"] == "HOT"
    assert node.current_order["items"][0]["quantity"] == 2


def test_correction_followup_uses_explicit_quantity_not_hallucinated_menu():
    node = make_node(
        current_order=order(menu="카페라떼", temperature="HOT", quantity=1),
    )

    first = node.make_decision(nlu("아니요"))
    assert first["decision"] == "MODIFY_ORDER"
    assert node.state == "ORDER_CORRECTION"

    result = node.make_decision(
        nlu(
            "3잔이라고",
            intent="ORDER",
            confidence=0.99,
            needs_reprompt=False,
            order_status="VALID",
            items=[
                {
                    "menu": "아메리카노",
                    "temperature": "HOT",
                    "quantity": 3,
                }
            ],
            explicit_slots={
                "menu": None,
                "temperature": None,
                "quantity": 3,
            },
        )
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert node.current_order["items"][0]["menu"] == "카페라떼"
    assert node.current_order["items"][0]["temperature"] == "HOT"
    assert node.current_order["items"][0]["quantity"] == 3


def test_modify_named_item_after_declining_finish_prompt():
    active_order = order(menu="카페라떼", temperature="HOT", quantity=3)
    node = make_node(state="WAIT_NEXT_CUSTOMER", current_order=active_order)

    node.make_decision(nlu("아니요"))
    assert node.state == "ORDER_LISTEN"

    result = node.make_decision(
        nlu(
            "아까 시킨 카페라떼 두 잔으로 바꾼다고요",
            intent="MODIFY",
            confidence=0.99,
            needs_reprompt=False,
            order_status="VALID",
            items=[
                {
                    "menu": "카페라떼",
                    "temperature": "HOT",
                    "quantity": 2,
                }
            ],
            explicit_slots={
                "menu": "카페라떼",
                "temperature": None,
                "quantity": 2,
            },
        )
    )

    assert result["decision"] == "CONFIRM_ORDER"
    assert node.current_order["items"][0]["menu"] == "카페라떼"
    assert node.current_order["items"][0]["quantity"] == 2


def test_action_listens_for_finish_question_but_not_after_idle():
    assert "ORDER_CONFIRMED" in OrderHandoffActionNode.LISTEN_AFTER_TTS_DECISIONS
    assert "CONTINUE_ORDER" in OrderHandoffActionNode.LISTEN_AFTER_TTS_DECISIONS
    assert "NEXT_CUSTOMER_READY" not in OrderHandoffActionNode.LISTEN_AFTER_TTS_DECISIONS


def test_vad_no_speech_status_requests_stt_retry():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)
    failures = []
    node.handle_stt_failed = failures.append

    node.stt_status_callback(SimpleNamespace(data="no_speech"))

    assert failures == ["no_speech"]


def test_vad_progress_statuses_do_not_request_retry():
    node = OrderHandoffActionNode.__new__(OrderHandoffActionNode)
    failures = []
    node.handle_stt_failed = failures.append

    for status in ("ready", "listening", "speech_detected", "transcribing", "done"):
        node.stt_status_callback(SimpleNamespace(data=status))

    assert failures == []
