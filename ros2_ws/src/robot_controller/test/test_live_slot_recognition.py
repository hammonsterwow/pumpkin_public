from robot_controller.dialogue_slots import (
    extract_explicit_slots,
    extract_temperature,
)


def test_quantity_nearest_single_surviving_menu_wins():
    slots = extract_explicit_slots("한 잔이랑 바닐라라떼 15 잔.")

    assert slots["menu"] == "바닐라라떼"
    assert slots["menus"] == ["바닐라라떼"]
    assert slots["quantity"] == 15


def test_normal_single_menu_quantity_is_unchanged():
    slots = extract_explicit_slots("바닐라라떼 한 잔 주세요.")

    assert slots["menu"] == "바닐라라떼"
    assert slots["quantity"] == 1


def test_quantity_before_single_menu_is_used_when_no_following_quantity_exists():
    slots = extract_explicit_slots("두 잔 바닐라라떼 주세요.")

    assert slots["menu"] == "바닐라라떼"
    assert slots["quantity"] == 2


def test_live_hot_transcript_haseyoro_is_recovered():
    assert extract_temperature("하세요로.") == "HOT"


def test_live_hot_transcript_deusin_geollo_is_recovered():
    assert extract_temperature("드신 걸로 주세요.") == "HOT"


def test_colloquial_hot_phrase_is_recovered():
    assert extract_temperature("뜨신 걸로 주세요.") == "HOT"


def test_live_hot_aliases_do_not_match_inside_unrelated_long_sentence():
    assert extract_temperature("아까 드신 걸로 주문 내역을 확인할게요.") is None
