"""One-shot ingestion: orders CSV + policy PDFs.

  python -m app.ingest.run_all            # uses /data defaults
  python -m app.ingest.run_all <docs_dir> <orders_csv>
"""
from __future__ import annotations

import os
import sys

from app.core.db import init_pool
from app.ingest.load_documents import load_documents
from app.ingest.load_orders import load_orders


def main() -> None:
    docs_dir = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DOCS_DIR", "/data/documents")
    orders_csv = sys.argv[2] if len(sys.argv) > 2 else os.getenv("ORDERS_CSV", "/data/orders.csv")

    init_pool()
    n_orders = load_orders(orders_csv)
    n_chunks = load_documents(docs_dir)
    print(f"[ingest] orders={n_orders} rows, documents={n_chunks} chunks. Done.")


if __name__ == "__main__":
    main()
