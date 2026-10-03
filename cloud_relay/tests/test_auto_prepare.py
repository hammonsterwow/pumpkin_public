from datetime import datetime, timedelta, timezone

from cloud_relay.main import project_auto_status


def test_app_order_follows_demo_timeline_without_pos():
    created = datetime(2026, 9, 28, tzinfo=timezone.utc)
    order = {
        "source": "APP",
        "auto_prepare": True,
        "status": "RECEIVED",
        "created_at": created,
        "updated_at": created,
    }
    cases = [
        (0, "RECEIVED"),
        (0.99, "RECEIVED"),
        (1, "PREPARING"),
        (5.99, "PREPARING"),
        (6, "READY"),
    ]
    for elapsed, status in cases:
        projected = project_auto_status(order, created + timedelta(seconds=elapsed))
        assert projected["status"] == status


def test_manual_and_non_demo_orders_are_not_advanced():
    created = datetime(2026, 9, 28, tzinfo=timezone.utc)
    order = {
        "source": "APP",
        "auto_prepare": True,
        "status": "RECEIVED",
        "created_at": created,
        "updated_at": created,
    }
    later = created + timedelta(minutes=1)
    for change in (
        {"status": "CANCELLED"},
        {"status": "PICKED_UP"},
        {"auto_prepare": False},
        {"source": "ROBOT"},
    ):
        unchanged = {**order, **change}
        assert project_auto_status(unchanged, later) == unchanged
