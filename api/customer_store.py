from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "customers.sqlite3"
_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_customer_db() -> None:
    with _DB_LOCK, _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                preferred_menu TEXT NOT NULL DEFAULT '',
                preferred_temperature TEXT NOT NULL DEFAULT 'NONE',
                preferred_quantity INTEGER NOT NULL DEFAULT 1,
                visit_count INTEGER NOT NULL DEFAULT 0,
                face_registered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def _row_to_customer(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "customer_id": row["customer_id"],
        "name": row["name"],
        "preferred_menu": row["preferred_menu"],
        "preferred_temperature": row["preferred_temperature"],
        "preferred_quantity": row["preferred_quantity"],
        "visit_count": row["visit_count"],
        "face_registered": bool(row["face_registered"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_customers() -> list[dict[str, Any]]:
    initialize_customer_db()
    with _DB_LOCK, _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM customers ORDER BY updated_at DESC, customer_id ASC"
        ).fetchall()
    return [_row_to_customer(row) for row in rows]


def get_customer(customer_id: str) -> dict[str, Any] | None:
    initialize_customer_db()
    with _DB_LOCK, _connect() as connection:
        row = connection.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    return _row_to_customer(row) if row else None


def create_customer(payload: dict[str, Any]) -> dict[str, Any]:
    initialize_customer_db()
    customer_id = str(payload.get("customer_id") or f"customer_{uuid.uuid4().hex[:8]}").strip()
    now = _now_iso()
    values = (
        customer_id,
        str(payload["name"]).strip(),
        str(payload.get("preferred_menu") or "").strip(),
        str(payload.get("preferred_temperature") or "NONE").upper(),
        max(1, int(payload.get("preferred_quantity") or 1)),
        max(0, int(payload.get("visit_count") or 0)),
        1 if payload.get("face_registered") else 0,
        now,
        now,
    )

    try:
        with _DB_LOCK, _connect() as connection:
            connection.execute(
                """
                INSERT INTO customers (
                    customer_id, name, preferred_menu, preferred_temperature,
                    preferred_quantity, visit_count, face_registered,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            connection.commit()
    except sqlite3.IntegrityError as error:
        raise ValueError(f"이미 존재하는 고객 ID입니다: {customer_id}") from error

    customer = get_customer(customer_id)
    if customer is None:
        raise RuntimeError("고객 저장 후 조회에 실패했습니다.")
    return customer


def update_customer(customer_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    current = get_customer(customer_id)
    if current is None:
        return None

    updated = {
        **current,
        **{key: value for key, value in payload.items() if value is not None},
    }
    updated_at = _now_iso()

    with _DB_LOCK, _connect() as connection:
        connection.execute(
            """
            UPDATE customers
            SET name = ?, preferred_menu = ?, preferred_temperature = ?,
                preferred_quantity = ?, visit_count = ?, face_registered = ?,
                updated_at = ?
            WHERE customer_id = ?
            """,
            (
                str(updated["name"]).strip(),
                str(updated.get("preferred_menu") or "").strip(),
                str(updated.get("preferred_temperature") or "NONE").upper(),
                max(1, int(updated.get("preferred_quantity") or 1)),
                max(0, int(updated.get("visit_count") or 0)),
                1 if updated.get("face_registered") else 0,
                updated_at,
                customer_id,
            ),
        )
        connection.commit()

    return get_customer(customer_id)


def delete_customer(customer_id: str) -> bool:
    initialize_customer_db()
    with _DB_LOCK, _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM customers WHERE customer_id = ?", (customer_id,)
        )
        connection.commit()
        return cursor.rowcount > 0
