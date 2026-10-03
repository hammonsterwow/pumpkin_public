from __future__ import annotations

from copy import deepcopy

from robot_controller.dialogue_act_resolver import DialogueActResolver
from robot_controller.order_dialogue_manager import OrderDialogueManager
from robot_controller.response_manager import ResponseManager


def test_dialogue_act_resolver_handles_state_dependent_language():
    resolver = DialogueActResolver()

    assert resolver.resolve_command({"text": "주문 취소할게요"}) == "CANCEL"
    assert resolver.resolve_command({"text": "처음부터 다시 주문할게요"}) == "RESTART"
    assert resolver.is_additional_order_request({"text": "하나 더 주문할게요"})
    assert resolver.is_correction_request(
        {"text": "3잔이라고", "intent": "ORDER"}
    )
    assert resolver.resolve_confirmation(
        {"text": "넵"},
        state="ORDER_CONFIRM",
        confirmation_states={"ORDER_CONFIRM"},
    ) == "AFFIRM"
    assert resolver.resolve_confirmation(
        {"text": "넵"},
        state="ORDER_LISTEN",
        confirmation_states={"ORDER_CONFIRM"},
    ) is None


def test_confirmation_accepts_filler_prefixed_repetition_and_clear_suffix():
    resolver = DialogueActResolver()
    states = {"ORDER_CONFIRM"}

    assert resolver.resolve_confirmation(
        {"text": "어 맞아요 맞아요", "intent": "AFFIRM", "confidence": 0.9922},
        state="ORDER_CONFIRM",
        confirmation_states=states,
    ) == "AFFIRM"
    assert resolver.resolve_confirmation(
        {"text": "그렇게.. 아니요!", "intent": "DENY", "confidence": 0.7502},
        state="ORDER_CONFIRM",
        confirmation_states=states,
    ) == "DENY"


def test_confirmation_model_fallback_requires_high_confidence():
    resolver = DialogueActResolver()
    states = {"ORDER_CONFIRM"}

    assert resolver.resolve_confirmation(
        {"text": "그러게요", "intent": "AFFIRM", "confidence": 0.95},
        state="ORDER_CONFIRM",
        confirmation_states=states,
    ) == "AFFIRM"
    assert resolver.resolve_confirmation(
        {"text": "그러게요", "intent": "AFFIRM", "confidence": 0.89},
        state="ORDER_CONFIRM",
        confirmation_states=states,
    ) is None


def test_modify_intent_requires_cue_or_high_confidence():
    resolver = DialogueActResolver()

    # Physical-test false positive: background speech must not become correction
    # merely because the learned intent head weakly predicts MODIFY.
    assert not resolver.is_correction_request({
        "text": "수업도 기록해서",
        "intent": "MODIFY",
        "confidence": 0.621,
    })

    # Explicit correction language remains authoritative even with a weak model
    # score so genuine requests such as "수정할게요" are not lost.
    assert resolver.is_correction_request({
        "text": "수정할게요",
        "intent": "MODIFY",
        "confidence": 0.55,
    })
    assert resolver.is_correction_request({
        "text": "아메리카노로 바꿀게요",
        "intent": "ORDER",
        "confidence": 0.40,
    })

    # Model-only MODIFY is still available, but only at deliberately high
    # confidence when there is no literal correction cue in the transcript.
    assert resolver.is_correction_request({
        "text": "그걸로 할래요",
        "intent": "MODIFY",
        "confidence": 0.95,
    })
    assert not resolver.is_correction_request({
        "text": "그걸로 할래요",
        "intent": "MODIFY",
        "confidence": 0.89,
    })


def test_order_manager_prefers_explicit_correction_slots():
    manager = OrderDialogueManager()
    nlu_result = {
        "items": [
            {
                "menu": "아메리카노",
                "temperature": "HOT",
                "quantity": 3,
            }
        ],
        "explicit_slots": {
            "menu": None,
            "temperature": None,
            "quantity": 3,
        },
    }

    incoming = manager.extract_incoming_items(
        nlu_result,
        prefer_explicit=True,
    )

    assert incoming[0]["menu"] is None
    assert incoming[0]["temperature"] is None
    assert incoming[0]["quantity"] == 3


def test_order_manager_updates_quantity_without_renaming_existing_menu():
    manager = OrderDialogueManager()
    current = [
        {
            "item_id": 0,
            "menu": "카페라떼",
            "temperature": "HOT",
            "quantity": 1,
            "missing_slots": [],
            "validation_errors": [],
        }
    ]
    incoming = [
        {
            "item_id": 0,
            "menu": None,
            "temperature": None,
            "quantity": 3,
            "missing_slots": ["menu", "temperature"],
            "validation_errors": [],
        }
    ]

    merged = manager.merge_order_items(
        current,
        incoming,
        waiting_for=None,
        overwrite=True,
    )

    assert merged[0]["menu"] == "카페라떼"
    assert merged[0]["temperature"] == "HOT"
    assert merged[0]["quantity"] == 3


def test_response_manager_preserves_full_contract_by_default():
    manager = ResponseManager()
    decision = {
        "decision": "CONFIRM_ORDER",
        "response_key": "confirm_order",
        "response_args": {},
        "reason": "all_slots_filled",
        "state": "ORDER_CONFIRM",
        "session_id": "session-1",
        "order": {
            "items": [
                {
                    "menu": "카페라떼",
                    "temperature": "HOT",
                    "quantity": 2,
                }
            ],
            "order_status": "VALID",
        },
        "nlu_result": {"text": "카페라떼 두 잔"},
    }
    original = deepcopy(decision)

    response = manager.render(decision)

    assert response["speech"] == "따뜻한 카페라떼 2잔 맞으신가요?"
    assert response["display_text"] == "따뜻한 카페라떼 2잔"
    assert response["order"] == decision["order"]
    assert response["nlu_result"] == decision["nlu_result"]
    assert decision == original


def test_compact_response_keeps_hardware_fields_and_omits_raw_nlu():
    manager = ResponseManager()
    decision = {
        "decision": "CONFIRM_ORDER",
        "response_key": "confirm_order",
        "response_args": {},
        "reason": "all_slots_filled",
        "state": "ORDER_CONFIRM",
        "session_id": "session-1",
        "order": {
            "items": [
                {
                    "menu": "아메리카노",
                    "temperature": "ICE",
                    "quantity": 1,
                }
            ],
            "order_status": "VALID",
        },
        "nlu_result": {"text": "아이스 아메리카노 하나"},
    }

    response = manager.render(decision, include_debug_context=False)

    assert response["decision"] == "CONFIRM_ORDER"
    assert response["response_args"] == {}
    assert response["reason"] == "all_slots_filled"
    assert response["speech"] == "아이스 아메리카노 1잔 맞으신가요?"
    assert response["display_text"] == "아이스 아메리카노 1잔"
    assert response["order_summary"]["items"] == decision["order"]["items"]
    assert "nlu_result" not in response
    assert "order" not in response


def test_legacy_finish_response_key_remains_renderable():
    manager = ResponseManager()

    canonical = manager.render_speech("ask_finish_order", {})
    legacy = manager.render_speech("ask_next_customer", {})

    assert canonical == "주문을 마치시겠어요?"
    assert legacy == canonical
