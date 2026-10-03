import json

import robot_controller.preorder as preorder_module
from robot_controller.preorder import PreorderApiClient, select_active_preorder
from robot_controller.response_manager import ResponseManager


def test_ready_app_preorder_has_priority_for_customer():
    orders = [
        {
            "order_id": "received",
            "customer_id": "uid-1",
            "source": "APP",
            "status": "RECEIVED",
            "created_at": "2026-08-14T10:00:00+00:00",
            "items": [{"menu_name": "아메리카노", "quantity": 1}],
        },
        {
            "order_id": "ready",
            "customer_id": "uid-1",
            "source": "APP",
            "status": "READY",
            "created_at": "2026-08-14T09:00:00+00:00",
            "items": [{"menu_name": "레몬에이드", "quantity": 2}],
        },
    ]
    assert select_active_preorder(orders, "uid-1")["order_id"] == "ready"


def test_terminal_and_other_customer_orders_are_ignored():
    orders = [
        {"customer_id": "uid-1", "source": "APP", "status": "PICKED_UP", "items": [{}]},
        {"customer_id": "uid-2", "source": "APP", "status": "READY", "items": [{}]},
        {"customer_id": "uid-1", "source": "ROBOT", "status": "READY", "items": [{}]},
    ]
    assert select_active_preorder(orders, "uid-1") is None


def test_ready_preorder_speech_uses_real_items_and_pickup_side():
    speech = ResponseManager().render_speech(
        "preorder_pickup_ready",
        {
            "response_args": {
                "customer_name": "a",
                "items": [
                    {
                        "menu_name": "레몬에이드",
                        "temperature": "ICE",
                        "quantity": 2,
                    }
                ],
            }
        },
    )
    assert speech == "a님, 사전 주문하신 아이스 레몬에이드 두 잔이 왼쪽 음료 수령대에 준비되어 있습니다."


def test_mark_picked_up_uses_authenticated_status_patch(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "order_id": "order-ready",
                "status": "PICKED_UP",
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(preorder_module, "urlopen", fake_urlopen)
    client = PreorderApiClient(
        base_url="https://relay.example",
        token="secret-token",
    )

    result = client.mark_picked_up("order-ready")

    assert result.error is None
    assert result.order == {"order_id": "order-ready", "status": "PICKED_UP"}
    assert captured["url"] == "https://relay.example/api/v1/orders/order-ready/status"
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"status": "PICKED_UP"}
    assert captured["headers"]["X-relay-token"] == "secret-token"
