"""Schema description handed to the LLM for text-to-SQL.

Keeping this explicit (column types, the exact status vocabulary, the order_id
format, and the fixed business date) is what stops the model from inventing
columns or mis-formatting WHERE clauses.
"""
from __future__ import annotations

from app.core.config import settings

SCHEMA_PROMPT = f"""You write a SINGLE PostgreSQL SELECT query against this schema.

Table: orders
  order_id    TEXT     -- primary key, format 'ORD-1001' (literal 'ORD-' prefix). NEVER treat as integer.
  customer    TEXT     -- full name, e.g. 'Aarav Sharma'
  product     TEXT     -- one of: Mechanical Keyboard, Bluetooth Speaker, Laptop Stand,
                       --   USB-C Hub, Monitor Arm, Ergonomic Chair Cushion, Webcam 1080p,
                       --   Noise-Cancelling Headphones, Wireless Mouse, Portable SSD 1TB
  amount      INTEGER  -- order value in whole Indian Rupees (INR)
  status      TEXT     -- exactly one of: pending, processing, shipped, delivered, cancelled, returned
  order_date  DATE     -- ISO date; data spans 2025-12-17 to 2026-06-14

Rules:
- The business "today" is {settings.business_today}. Resolve relative dates
  ("last month", "this year", "last 30 days") against THIS date, not the real clock.
  Example: "last month" = the full calendar month of May 2026.
- Use case-insensitive matching for free-text filters (ILIKE) on customer/product.
- For revenue/totals use SUM(amount); for counts use COUNT(*).
- Return only the columns needed to answer the question.
- Output ONLY the SQL. No prose, no markdown fences, no trailing semicolon.
- If the question cannot be answered from this single table, output exactly: NO_QUERY
"""
