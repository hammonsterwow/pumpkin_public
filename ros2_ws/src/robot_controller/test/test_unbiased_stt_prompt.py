from robot_controller.stt_node_unbiased import UnbiasedSTTNode


def test_production_stt_never_supplies_an_initial_prompt():
    assert UnbiasedSTTNode.select_initial_prompt(
        "normal",
        "MENU ORDER PROMPT",
        "CONFIRMATION PROMPT",
    ) is None
    assert UnbiasedSTTNode.select_initial_prompt(
        "confirmation",
        "MENU ORDER PROMPT",
        "CONFIRMATION PROMPT",
    ) is None


def test_observed_confirmation_prompt_leak_is_rejected():
    text = (
        "두 잔을 고치면 아메리카노, 카페라떼, 딸기스무디, "
        "레몬에이드 중 하나를 말합니다."
    )

    assert UnbiasedSTTNode.looks_like_legacy_prompt_leak(text) is True

    node = UnbiasedSTTNode.__new__(UnbiasedSTTNode)
    assert node.should_reject_text(text) is True


def test_full_old_confirmation_prompt_is_rejected():
    text = (
        "한국어 카페 주문 확인 대화입니다. 짧은 확인 답변은 네, 예, 응, "
        "아니요, 아뇨입니다. 메뉴를 고치면 아메리카노, 카페라떼, "
        "바닐라라떼, 딸기스무디, 레몬에이드 중 하나를 말합니다."
    )
    assert UnbiasedSTTNode.looks_like_legacy_prompt_leak(text) is True


def test_real_multi_menu_order_is_not_mistaken_for_prompt_leak():
    text = "아메리카노 두 잔이랑 카페라떼 한 잔, 레몬에이드 한 잔 주세요."

    assert UnbiasedSTTNode.looks_like_legacy_prompt_leak(text) is False

    node = UnbiasedSTTNode.__new__(UnbiasedSTTNode)
    assert node.should_reject_text(text) is False


def test_normal_confirmation_is_not_rejected():
    node = UnbiasedSTTNode.__new__(UnbiasedSTTNode)
    for text in ("네", "맞아요", "아니요", "두 잔이요"):
        assert UnbiasedSTTNode.looks_like_legacy_prompt_leak(text) is False
        assert node.should_reject_text(text) is False
