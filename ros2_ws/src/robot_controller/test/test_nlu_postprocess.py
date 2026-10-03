from copy import deepcopy

from robot_controller.nlu_postprocess import (
    clear_unexpressed_temperature_predictions,
)


def make_result(menu, temperature, *, order_status="VALID"):
    missing_slots = [] if temperature is not None else ["temperature"]
    return {
        "intent": "ORDER",
        "order_status": order_status,
        "needs_reprompt": False,
        "items": [
            {
                "item_id": 0,
                "menu": menu,
                "temperature": temperature,
                "quantity": 1,
                "missing_slots": missing_slots,
            }
        ],
    }


def test_clears_hot_prediction_when_temperature_was_not_expressed():
    result = make_result("아메리카노", "HOT")

    changed = clear_unexpressed_temperature_predictions(
        result,
        {"menu": "아메리카노", "temperature": None, "quantity": 1},
    )

    assert changed is True
    assert result["items"][0]["temperature"] is None
    assert result["items"][0]["temperature_prediction_ignored"] == "HOT"
    assert "temperature" in result["items"][0]["missing_slots"]
    assert result["order_status"] == "INCOMPLETE"
    assert result["needs_reprompt"] is True


def test_keeps_explicit_hot_prediction():
    result = make_result("아메리카노", "HOT")
    original = deepcopy(result)

    changed = clear_unexpressed_temperature_predictions(
        result,
        {"menu": "아메리카노", "temperature": "HOT", "quantity": 1},
    )

    assert changed is False
    assert result == original


def test_keeps_ice_default_for_ice_only_menu():
    result = make_result("딸기스무디", "ICE")
    original = deepcopy(result)

    changed = clear_unexpressed_temperature_predictions(
        result,
        {"menu": "딸기스무디", "temperature": None, "quantity": 1},
    )

    assert changed is False
    assert result == original


def test_does_not_change_already_missing_temperature():
    result = make_result("카페라떼", None, order_status="INCOMPLETE")
    original = deepcopy(result)

    changed = clear_unexpressed_temperature_predictions(result, None)

    assert changed is False
    assert result == original
