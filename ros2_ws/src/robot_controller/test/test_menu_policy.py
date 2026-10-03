from robot_controller.menu_policy import (
    MAX_QUANTITY,
    MODEL_MENU_LABELS,
    MODEL_QUANTITY_LABELS,
    MODEL_TEMPERATURE_LABELS,
    default_temperature,
    normalize_menu,
    normalize_quantity,
    normalize_temperature,
    validate_nlu_label_maps,
)


def make_id_to_label(labels):
    return {str(index): label for index, label in enumerate(sorted(labels))}


def test_normalizes_shared_menu_temperature_and_quantity_aliases():
    assert normalize_menu("레모네이드") == "레몬에이드"
    assert normalize_menu("라테") == "카페라떼"
    assert normalize_temperature("따듯하게") == "HOT"
    assert normalize_temperature("온으로") == "HOT"
    assert normalize_temperature("냉으로") == "ICE"
    assert normalize_temperature("ICED") == "ICE"
    assert normalize_quantity("두 잔") == 2
    assert normalize_quantity("열한 잔") == 11
    assert normalize_quantity("스무 잔") == MAX_QUANTITY
    assert normalize_quantity(str(MAX_QUANTITY)) == MAX_QUANTITY
    assert normalize_quantity(MAX_QUANTITY + 1) is None


def test_applies_cold_only_default_from_policy():
    assert default_temperature("레몬에이드") == "ICE"
    assert default_temperature("딸기스무디") == "ICE"
    assert default_temperature("아메리카노") is None


def test_accepts_matching_nlu_checkpoint_label_maps():
    label_maps = {
        "menu": {"id2label": make_id_to_label(MODEL_MENU_LABELS)},
        "temperature": {
            "id2label": make_id_to_label(MODEL_TEMPERATURE_LABELS)
        },
        "quantity": {"id2label": make_id_to_label(MODEL_QUANTITY_LABELS)},
    }

    assert validate_nlu_label_maps(label_maps) == []


def test_reports_checkpoint_labels_that_do_not_match_policy():
    label_maps = {
        "menu": {"id2label": {"0": "NONE", "1": "아메리카노"}},
        "temperature": {"id2label": {"0": "NONE", "1": "ICE", "2": "HOT"}},
        "quantity": {"id2label": make_id_to_label(MODEL_QUANTITY_LABELS)},
    }

    errors = validate_nlu_label_maps(label_maps)

    assert len(errors) == 1
    assert errors[0].startswith("menu:")
    assert "카페라떼" in errors[0]
