from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from api.schemas.order import (
    CreateOrderRequest,
    OrderItemResponse,
    OrderResponse,
    OrderSource,
    OrderStatus,
)


class SQLiteOrderRepository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        configured = database_path or os.getenv(
            "PUMPKIN_ORDER_DB_PATH",
            root_dir / "data/orders.sqlite3",
        )
        self.database_path = Path(configured)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    order_number TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    customer_id TEXT,
                    status TEXT NOT NULL,
                    original_text TEXT,
                    metadata_json TEXT NOT NULL,
                    total_price INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    menu_id TEXT NOT NULL,
                    menu_name TEXT NOT NULL,
                    temperature TEXT NOT NULL,
                    size TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    options_json TEXT NOT NULL,
                    unit_price INTEGER NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
                );
                """
            )

    def _next_order_number(self, connection: sqlite3.Connection) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"ORD-{today}-"
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE order_number LIKE ?",
            (f"{prefix}%",),
        ).fetchone()
        sequence = int(row["count"]) + 1
        return f"{prefix}{sequence:03d}"

    def create(self, payload: CreateOrderRequest) -> OrderResponse:
        existing = self.find_by_request_id(payload.request_id)
        if existing is not None:
            return existing

        order_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        total_price = sum(item.unit_price * item.quantity for item in payload.items)

        with self._connect() as connection:
            order_number = self._next_order_number(connection)
            connection.execute(
                """
                INSERT INTO orders (
                    id, order_number, request_id, source, customer_id, status,
                    original_text, metadata_json, total_price, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    order_number,
                    payload.request_id,
                    payload.source.value,
                    payload.customer_id,
                    OrderStatus.RECEIVED.value,
                    payload.original_text,
                    json.dumps(payload.metadata, ensure_ascii=False),
                    total_price,
                    now,
                    now,
                ),
            )

            for item in payload.items:
                connection.execute(
                    """
                    INSERT INTO order_items (
                        id, order_id, menu_id, menu_name, temperature, size,
                        quantity, options_json, unit_price
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        order_id,
                        item.menu_id,
                        item.menu_name,
                        item.temperature,
                        item.size,
                        item.quantity,
                        json.dumps(item.options, ensure_ascii=False),
                        item.unit_price,
                    ),
                )

        created = self.find_by_id(order_id)
        if created is None:
            raise RuntimeError("생성된 주문을 다시 조회하지 못했습니다.")
        return created

    def list(self) -> list[OrderResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM orders ORDER BY created_at DESC"
            ).fetchall()
        return [order for row in rows if (order := self.find_by_id(row["id"])) is not None]

    def find_by_id(self, order_id: str) -> OrderResponse | None:
        with self._connect() as connection:
            order = connection.execute(
                "SELECT * FROM orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            if order is None:
                return None

            item_rows = connection.execute(
                "SELECT * FROM order_items WHERE order_id = ? ORDER BY rowid",
                (order_id,),
            ).fetchall()

        return OrderResponse(
            order_id=order["id"],
            order_number=order["order_number"],
            request_id=order["request_id"],
            source=OrderSource(order["source"]),
            customer_id=order["customer_id"],
            status=OrderStatus(order["status"]),
            items=[
                OrderItemResponse(
                    id=item["id"],
                    menu_id=item["menu_id"],
                    menu_name=item["menu_name"],
                    temperature=item["temperature"],
                    size=item["size"],
                    quantity=item["quantity"],
                    options=json.loads(item["options_json"]),
                    unit_price=item["unit_price"],
                )
                for item in item_rows
            ],
            original_text=order["original_text"],
            metadata=json.loads(order["metadata_json"]),
            total_price=order["total_price"],
            created_at=datetime.fromisoformat(order["created_at"]),
            updated_at=datetime.fromisoformat(order["updated_at"]),
        )

    def find_by_request_id(self, request_id: str) -> OrderResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM orders WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return None if row is None else self.find_by_id(row["id"])

    def update_status(self, order_id: str, status: OrderStatus) -> OrderResponse | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, order_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.find_by_id(order_id)
