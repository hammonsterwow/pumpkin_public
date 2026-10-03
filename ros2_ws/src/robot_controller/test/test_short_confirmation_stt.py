from robot_controller.action_node_order_handoff import OrderHandoffActionNode
from robot_controller.stt_node import (
    DEFAULT_CONFIRMATION_INITIAL_PROMPT,
    DEFAULT_INITIAL_PROMPT,
    STTNode,
)


def test_repeated_short_affirmation_is_recovered_before_noise_rejection():
    assert STTNode.normalize_short_confirmation("네네네네네네") == "네"
    assert STTNode.normalize_short_confirmation("네 네 네 네") == "네"
    assert STTNode.normalize_short_confirmation("예예예예") == "예"
    assert STTNode.normalize_short_confirmation("응응응응") == "응"


def test_elongated_short_affirmation_is_recovered_before_noise_rejection():
    assert STTNode.normalize_short_confirmation("네에에에에에에") == "네"
    assert STTNode.normalize_short_confirmation("예에에에") == "예"
    assert STTNode.normalize_short_confirmation("응으으으") == "응"


def test_repeated_short_denial_is_recovered_before_noise_rejection():
    assert STTNode.normalize_short_confirmation("아니요아니요아니요") == "아니요"
    assert STTNode.normalize_short_confirmation("아뇨아뇨") == "아뇨"
    assert STTNode.normalize_short_confirmation("아니아니아니") == "아니요"


def test_elongated_short_denial_is_recovered_before_noise_rejection():
    assert STTNode.normalize_short_confirmation("아니이이요") == "아니요"
    assert STTNode.normalize_short_confirmation("아니요오오") == "아니요"
    assert STTNode.normalize_short_confirmation("아뇨오오") == "아뇨"


def test_non_confirmation_repetition_is_not_rewritten():
    assert STTNode.normalize_short_confirmation("하하하하") == "하하하하"
    assert STTNode.normalize_short_confirmation("네이버") == "네이버"


def test_confirmation_words_are_allowed_by_stt_noise_filter():
    node = STTNode.__new__(STTNode)
    for text in ("네", "예", "응", "아니", "아니요", "아뇨"):
        assert node.should_reject_text(text) is False


def test_default_prompt_does_not_overweight_americano_examples():
    assert DEFAULT_INITIAL_PROMPT.count("아메리카노") == 1
    assert "아아는 아이스 아메리카노" not in DEFAULT_INITIAL_PROMPT
    assert "아이스 아메리카노 한 잔 주세요" not in DEFAULT_INITIAL_PROMPT
    assert "딸기스무디" in DEFAULT_INITIAL_PROMPT
    assert "스무 잔" in DEFAULT_INITIAL_PROMPT


def test_confirmation_prompt_prioritizes_short_answers_but_keeps_corrections():
    for answer in ("네", "예", "응", "아니요", "아뇨"):
        assert answer in DEFAULT_CONFIRMATION_INITIAL_PROMPT
    for menu in ("아메리카노", "카페라떼", "바닐라라떼", "딸기스무디", "레몬에이드"):
        assert menu in DEFAULT_CONFIRMATION_INITIAL_PROMPT
    assert "스무 잔" in DEFAULT_CONFIRMATION_INITIAL_PROMPT


def test_confirmation_duration_is_capped_without_shortening_normal_orders():
    assert STTNode.select_max_speech_duration("normal", 10.0, 3.5) == 10.0
    assert STTNode.select_max_speech_duration("confirmation", 10.0, 3.5) == 3.5
    assert STTNode.select_max_speech_duration("confirmation", 3.0, 3.5) == 3.0


def test_listen_mode_selects_matching_whisper_prompt():
    assert STTNode.select_initial_prompt(
        "normal", "ORDER_PROMPT", "CONFIRM_PROMPT"
    ) == "ORDER_PROMPT"
    assert STTNode.select_initial_prompt(
        "confirmation", "ORDER_PROMPT", "CONFIRM_PROMPT"
    ) == "CONFIRM_PROMPT"


def test_live_duplicated_smoothie_artifact_is_rejected_before_nlu():
    node = STTNode.__new__(STTNode)

    assert node.should_reject_text(
        "아이스 아메리카노 스무디 스무디 한 잔 주세요."
    ) is True
    assert node.should_reject_text("딸기스무디 스무 잔 주세요.") is False


def test_confirmation_decisions_use_short_vad_trigger():
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("CONFIRM_ORDER") == "confirm"
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("ORDER_CONFIRMED") == "confirm"
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("CONFIRM_ITEM") == "confirm"


def test_short_slot_and_correction_questions_use_short_vad_trigger():
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("ASK_MENU") == "confirm"
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("ASK_TEMPERATURE") == "confirm"
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("ASK_QUANTITY") == "confirm"
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("MODIFY_ORDER") == "confirm"


def test_stt_retry_preserves_confirmation_mode():
    assert (
        OrderHandoffActionNode.resolve_stt_trigger_mode(
            "STT_RETRY",
            previous_mode="confirm",
        )
        == "confirm"
    )
    assert (
        OrderHandoffActionNode.resolve_stt_trigger_mode(
            "STT_RETRY",
            previous_mode="start",
        )
        == "start"
    )


def test_only_free_form_order_start_keeps_normal_vad_trigger():
    assert OrderHandoffActionNode.resolve_stt_trigger_mode("START_ORDER") == "start"
