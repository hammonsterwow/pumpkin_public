from pathlib import Path

from robot_controller.order_submission_node import MenuCatalog
from robot_controller.order_api_client import ConfirmedOrder, ConfirmedOrderItem, OrderApiClient


def test_menu_catalog_maps_robot_item_to_official_snapshot():
    root = Path(__file__).resolve().parents[4]
    catalog = MenuCatalog(root / "config" / "menu_catalog.json")

    item = catalog.order_item({
        "menu": "레몬에이드",
        "temperature": "ICE",
        "quantity": 2,
    })

    assert item.menu_id == 4
    assert item.menu_name == "레몬에이드"
    assert item.unit_price == 4500
    assert item.quantity == 2


def test_robot_request_id_is_session_stable(monkeypatch):
    captured = []
    client = OrderApiClient(base_url="https://relay.example")
    monkeypatch.setattr(client, "_post_order", lambda payload: captured.append(payload) or payload)

    order = ConfirmedOrder(
        items=[
            ConfirmedOrderItem(
                menu_id=1,
                menu_name="아메리카노",
                temperature="ICE",
                quantity=1,
                unit_price=3000,
            )
        ],
        original_text=None,
        confidence=1.0,
        session_id="session-1234",
    )

    first = client.submit_confirmed_order(order)
    second = client.submit_confirmed_order(order)

    assert first["request_id"] == "robot-session-1234"
    assert second["request_id"] == "robot-session-1234"
    assert captured[0]["source"] == "ROBOT"
    assert captured[0]["items"][0]["menu_id"] == 1
    assert captured[0]["items"][0]["unit_price"] == 3000
