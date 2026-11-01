"""Truy cập PostgreSQL: connection pool, tạo bảng khi khởi động và các truy vấn CRUD."""

import logging
import time
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

log = logging.getLogger("catalogue.db")

# Schema do catalogue-service tự tạo (TV3 không cần quản lý migration).
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS products (
        id          SERIAL PRIMARY KEY,
        name        VARCHAR(255)  NOT NULL,
        price       NUMERIC(12,2) NOT NULL CHECK (price >= 0),
        description TEXT          DEFAULT '',
        stock       INTEGER       NOT NULL DEFAULT 0 CHECK (stock >= 0),
        created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)",
]

# Khóa advisory để nhiều replica khởi động cùng lúc không tranh nhau tạo bảng.
_SCHEMA_LOCK_ID = 727001

_COLUMNS = "id, name, description, price, stock"

pool: Optional[ConnectionPool] = None


def _row(row: dict[str, Any]) -> dict[str, Any]:
    """NUMERIC trả về Decimal, đổi sang float để JSON hóa; description null giữ nguyên."""
    row["price"] = float(row["price"])
    return row


def init_schema() -> None:
    """Chờ DB sẵn sàng (có retry) rồi tạo bảng nếu chưa có."""
    last_error: Optional[Exception] = None
    for attempt in range(1, settings.db_connect_retries + 1):
        try:
            with psycopg.connect(settings.conninfo, connect_timeout=5) as conn:
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_ID,))
                for statement in SCHEMA_STATEMENTS:
                    conn.execute(statement)
            log.info("Schema sẵn sàng (lần thử %d)", attempt)
            return
        except psycopg.OperationalError as exc:
            last_error = exc
            log.warning(
                "Chưa kết nối được PostgreSQL %s:%s (lần %d/%d): %s",
                settings.db_host,
                settings.db_port,
                attempt,
                settings.db_connect_retries,
                str(exc).strip(),
            )
            time.sleep(settings.db_connect_delay)
    raise RuntimeError(f"Không kết nối được PostgreSQL sau {settings.db_connect_retries} lần thử") from last_error


def open_pool() -> None:
    global pool
    pool = ConnectionPool(
        settings.conninfo,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        timeout=settings.db_pool_timeout,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    pool.open(wait=True, timeout=settings.db_pool_timeout)


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def ping() -> None:
    """Kiểm tra DB còn trả lời (dùng cho /ready). Ném exception nếu lỗi."""
    assert pool is not None
    with pool.connection() as conn:
        conn.execute("SELECT 1")


def list_products(limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    assert pool is not None
    with pool.connection() as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM products ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT count(*) AS n FROM products").fetchone()["n"]
    return [_row(r) for r in rows], total


def get_product(product_id: int) -> Optional[dict[str, Any]]:
    assert pool is not None
    with pool.connection() as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM products WHERE id = %s", (product_id,)
        ).fetchone()
    return _row(row) if row else None


def create_product(name: str, description: Optional[str], price: float, stock: int) -> dict[str, Any]:
    assert pool is not None
    with pool.connection() as conn:
        row = conn.execute(
            f"INSERT INTO products (name, description, price, stock) "
            f"VALUES (%s, %s, %s, %s) RETURNING {_COLUMNS}",
            (name, description, price, stock),
        ).fetchone()
    return _row(row)


def update_product(
    product_id: int, name: str, description: Optional[str], price: float, stock: int
) -> Optional[dict[str, Any]]:
    assert pool is not None
    with pool.connection() as conn:
        row = conn.execute(
            f"UPDATE products SET name = %s, description = %s, price = %s, stock = %s, "
            f"updated_at = now() WHERE id = %s RETURNING {_COLUMNS}",
            (name, description, price, stock, product_id),
        ).fetchone()
    return _row(row) if row else None


def delete_product(product_id: int) -> bool:
    assert pool is not None
    with pool.connection() as conn:
        row = conn.execute(
            "DELETE FROM products WHERE id = %s RETURNING id", (product_id,)
        ).fetchone()
    return row is not None
