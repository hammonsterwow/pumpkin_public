from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from .order_api_client import ConfirmedOrder, ConfirmedOrderItem, OrderApiClient


class MenuCatalog:
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        menus = payload.get("menus", [])
        if not isinstance(menus, list):
            raise ValueError("menu_catalog.json의 menus가 배열이 아닙니다.")

        self._by_label: dict[str, dict[str, Any]] = {}
        for raw in menus:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            labels = [name]
            aliases = raw.get("aliases", [])
            if isinstance(aliases, list):
                labels.extend(str(alias).strip() for alias in aliases)
            for label in labels:
                if label:
                    self._by_label[label] = raw

    def order_item(self, raw: dict[str, Any]) -> ConfirmedOrderItem:
        menu_name = str(raw.get("menu") or raw.get("menu_name") or "").strip()
        catalog_item = self._by_label.get(menu_name)
        if catalog_item is None:
            raise ValueError(f"공식 메뉴 카탈로그에서 찾을 수 없습니다: {menu_name!r}")
        if not bool(catalog_item.get("is_available", True)):
            raise ValueError(f"현재 판매 중이 아닌 메뉴입니다: {menu_name}")

        temperature = str(raw.get("temperature") or "NONE").upper()
        available_temperatures = {
            str(value).upper()
            for value in catalog_item.get("available_temperatures", [])
        }
        if temperature != "NONE" and temperature not in available_temperatures:
            raise ValueError(
                f"지원하지 않는 온도입니다: menu={menu_name}, temperature={temperature}"
            )

        quantity = int(raw.get("quantity") or 0)
        if quantity < 1:
            raise ValueError(f"수량이 올바르지 않습니다: menu={menu_name}, quantity={quantity}")

        return ConfirmedOrderItem(
            menu_id=int(catalog_item["menu_id"]),
            menu_name=str(catalog_item["name"]),
            temperature=temperature,
            quantity=quantity,
            size="NONE",
            options=[],
            unit_price=int(catalog_item.get("price") or 0),
        )


class OrderSubmissionNode(Node):
    """Submit one final ROBOT order after the customer finishes the session.

    ORDER_CONFIRMED is only a candidate because the current dialogue allows the
    customer to continue and add more drinks after that summary. The final Cloud
    Relay POST happens only when NEXT_CUSTOMER_READY + ORDER_FINISHED is emitted.
    """

    def __init__(self) -> None:
        super().__init__("order_submission_node")

        project_root = Path(
            os.getenv(
                "PUMPKIN_PROJECT_ROOT",
                str(Path(__file__).resolve().parents[4]),
            )
        )
        self.catalog = MenuCatalog(project_root / "config" / "menu_catalog.json")
        timeout = float(os.getenv("PUMPKIN_ORDER_API_TIMEOUT_SEC", "5.0"))
        self.client = OrderApiClient(timeout=timeout)

        self._candidate_orders: dict[str, dict[str, Any]] = {}
        self._submitted_sessions: set[str] = set()
        self._inflight_sessions: set[str] = set()
        self._lock = threading.Lock()

        self.create_subscription(String, "/decision_result", self.decision_callback, 20)
        self.get_logger().info(
            f"Robot order submission ready: {self.client.base_url}/api/v1/orders"
        )

    def decision_callback(self, msg: String) -> None:
        try:
            decision = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError) as exc:
            self.get_logger().warning(f"Invalid decision JSON: {exc}")
            return
        if not isinstance(decision, dict):
            return

        decision_name = str(decision.get("decision") or "").upper()
        session_id = str(decision.get("session_id") or "").strip()

        if decision_name == "ORDER_CONFIRMED":
            order = decision.get("order")
            if session_id and isinstance(order, dict):
                # A later ORDER_CONFIRMED in the same session replaces this
                # candidate, so additions/corrections are included in the final POST.
                with self._lock:
                    self._candidate_orders[session_id] = order
            return

        if decision_name == "CANCEL_ORDER" and session_id:
            with self._lock:
                self._candidate_orders.pop(session_id, None)
            return

        if (
            decision_name != "NEXT_CUSTOMER_READY"
            or str(decision.get("semantic_event") or "").upper() != "ORDER_FINISHED"
        ):
            return

        finished_session_id = str(
            decision.get("previous_session_id") or session_id
        ).strip()
        if not finished_session_id:
            self.get_logger().warning("ORDER_FINISHED에 session_id가 없습니다.")
            return

        with self._lock:
            if (
                finished_session_id in self._submitted_sessions
                or finished_session_id in self._inflight_sessions
            ):
                return
            order = self._candidate_orders.get(finished_session_id)
            if not isinstance(order, dict):
                self.get_logger().warning(
                    f"최종 제출할 주문 후보를 찾지 못했습니다: session={finished_session_id}"
                )
                return
            self._inflight_sessions.add(finished_session_id)

        threading.Thread(
            target=self._submit,
            args=(finished_session_id, order),
            daemon=True,
            name=f"robot-order-submit-{finished_session_id[:8]}",
        ).start()

    def _confirmed_order(
        self,
        session_id: str,
        raw_order: dict[str, Any],
    ) -> ConfirmedOrder:
        raw_items = raw_order.get("items", [])
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("최종 주문에 items가 없습니다.")

        items = [
            self.catalog.order_item(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        if len(items) != len(raw_items):
            raise ValueError("최종 주문 items 중 올바르지 않은 항목이 있습니다.")

        return ConfirmedOrder(
            items=items,
            original_text=None,
            confidence=float(raw_order.get("confidence") or 0.0),
            session_id=session_id,
            customer_id=None,
            schema_version=str(raw_order.get("schema_version") or "1.0"),
        )

    def _submit(self, session_id: str, raw_order: dict[str, Any]) -> None:
        try:
            created = self.client.submit_confirmed_order(
                self._confirmed_order(session_id, raw_order)
            )
            order_number = created.get("order_number") or created.get("order_id") or "?"
            status = created.get("status") or "?"
            self.get_logger().info(
                f"ROBOT 주문 Cloud Relay 등록 완료: {order_number}, status={status}"
            )
            with self._lock:
                self._submitted_sessions.add(session_id)
                self._candidate_orders.pop(session_id, None)
        except Exception as exc:  # noqa: BLE001 - keep ROS process alive on network failure
            self.get_logger().error(
                f"ROBOT 주문 Cloud Relay 등록 실패: session={session_id}, error={exc}"
            )
        finally:
            with self._lock:
                self._inflight_sessions.discard(session_id)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OrderSubmissionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
