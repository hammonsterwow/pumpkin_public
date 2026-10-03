from monitor_state import MonitorState


def item(menu=None, temperature=None, quantity=None, item_id=0):
    missing = []
    if menu is None:
        missing.append("menu")
    if temperature is None:
        missing.append("temperature")
    if quantity is None:
        missing.append("quantity")
    return {
        "item_id": item_id,
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
        "missing_slots": missing,
    }


def decision(name, items=None, waiting_for=None, session_id="session-1"):
    payload = {
        "decision": name,
        "state": name,
        "session_id": session_id,
        "waiting_for": waiting_for,
    }
    if items is not None:
        payload["order"] = {"items": items}
    return payload


def test_one_shot_order_keeps_all_slots():
    state = MonitorState()
    state.update_nlu({"items": [item("아메리카노", "ICE", 1)]})
    state.update_decision(decision("CONFIRM_ORDER", [item("아메리카노", "ICE", 1)]))

    shown = state.snapshot()["items"]
    assert shown == [item("아메리카노", "ICE", 1)]
    assert shown[0]["missing_slots"] == []


def test_missing_temperature_is_not_filled():
    state = MonitorState()
    partial = item("아메리카노", None, 1)
    state.update_nlu({"items": [partial]})
    state.update_decision(
        decision(
            "ASK_TEMPERATURE",
            [partial],
            waiting_for={"item_id": 0, "slot": "temperature"},
        )
    )

    shown = state.snapshot()["items"][0]
    assert shown["temperature"] is None
    assert "temperature" in shown["missing_slots"]


def test_missing_quantity_is_not_filled():
    state = MonitorState()
    partial = item("카페라떼", "HOT", None)
    state.update_decision(
        decision(
            "ASK_QUANTITY",
            [partial],
            waiting_for={"item_id": 0, "slot": "quantity"},
        )
    )

    shown = state.snapshot()["items"][0]
    assert shown["quantity"] is None
    assert "quantity" in shown["missing_slots"]


def test_additional_order_keeps_old_item_until_cumulative_decision_arrives():
    state = MonitorState()
    first = item("아메리카노", "ICE", 1, 0)
    added = item("카페라떼", "HOT", 1, 0)
    cumulative = [first, item("카페라떼", "HOT", 1, 1)]

    state.update_decision(decision("CONFIRM_ORDER", [first]))
    state.update_nlu({"items": [added]})
    assert state.snapshot()["items"] == [first]

    state.update_decision(decision("CONFIRM_ORDER", cumulative))
    assert state.snapshot()["items"] == cumulative


def test_multi_item_order_is_kept_as_separate_items():
    state = MonitorState()
    items = [
        item("아메리카노", "ICE", 2, 0),
        item("카페라떼", "HOT", 1, 1),
    ]
    state.update_decision(decision("CONFIRM_ORDER", items))

    shown = state.snapshot()["items"]
    assert len(shown) == 2
    assert shown[0]["menu"] == "아메리카노"
    assert shown[1]["menu"] == "카페라떼"


def test_stt_failure_does_not_create_order_values():
    state = MonitorState()
    state.update_stt_status("empty")
    state.update_decision(decision("STT_RETRY", items=None))

    assert state.snapshot()["items"] == []


def test_completion_keeps_last_confirmed_order_until_next_session():
    state = MonitorState()
    confirmed = [item("바닐라라떼", "ICE", 1)]
    state.update_decision(decision("CONFIRM_ORDER", confirmed))
    state.update_decision(decision("NEXT_CUSTOMER_READY", items=None))

    assert state.snapshot()["items"] == confirmed

    state.update_decision(decision("START_ORDER", items=None, session_id="session-2"))
    assert state.snapshot()["items"] == []
