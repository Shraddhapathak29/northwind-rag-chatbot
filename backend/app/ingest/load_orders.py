"""Load orders.csv into the `orders` table.

Run as a module:  python -m app.ingest.load_orders /data/orders.csv
Uses only the stdlib csv reader (no pandas) to keep the runtime image small.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from app.core.db import get_conn, init_pool
from app.ingest.ddl import ENABLE_PGVECTOR, ORDERS_DDL, TRUNCATE_ORDERS

EXPECTED_COLS = ["order_id", "customer", "product", "amount", "status", "order_date"]


def load_orders(csv_path: str) -> int:
    rows: list[tuple] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = set(EXPECTED_COLS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"orders.csv missing columns: {missing}")
        for r in reader:
            rows.append(
                (
                    r["order_id"].strip(),
                    r["customer"].strip(),
                    r["product"].strip(),
                    int(r["amount"]),
                    r["status"].strip().lower(),
                    r["order_date"].strip(),  # ISO yyyy-mm-dd -> DATE
                )
            )

    with get_conn() as conn:
        conn.execute(ENABLE_PGVECTOR)
        conn.execute(ORDERS_DDL)
        conn.execute(TRUNCATE_ORDERS)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO orders (order_id, customer, product, amount, status, order_date)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )
    return len(rows)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/data/orders.csv"
    if not Path(path).exists():
        sys.exit(f"orders csv not found: {path}")
    init_pool()
    n = load_orders(path)
    print(f"[load_orders] inserted {n} rows from {path}")
