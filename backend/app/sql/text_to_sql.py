"""Text-to-SQL tool: NL question -> safe SELECT -> executed result.

Returns a SqlResult that always serialises cleanly, even on failure, so the
agent can degrade gracefully ("I couldn't turn that into a query") instead of
crashing the stream.
"""
from __future__ import annotations

import datetime
import decimal

from app.core.config import settings
from app.core.db import get_conn
from app.core.llm import chat_extra, client
from app.models import SqlResult
from app.sql.guard import UnsafeSQLError, sanitize_sql
from app.sql.schema import SCHEMA_PROMPT


def _generate_sql(question: str) -> str:
    resp = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=[
            {"role": "system", "content": SCHEMA_PROMPT},
            {"role": "user", "content": question},
        ],
        **chat_extra(),
    )
    return (resp.choices[0].message.content or "").strip()


def _jsonable(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def query_orders(question: str) -> SqlResult:
    raw = _generate_sql(question)

    if raw.upper().startswith("NO_QUERY"):
        return SqlResult(
            sql="", columns=[], rows=[], row_count=0,
            error="The question cannot be answered from the orders table.",
        )

    try:
        sql = sanitize_sql(raw)
    except UnsafeSQLError as e:
        return SqlResult(sql=raw, columns=[], rows=[], row_count=0,
                         error=f"Rejected unsafe SQL: {e}")

    try:
        with get_conn() as conn:
            # Read-only + statement timeout: belt-and-braces around the guard.
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute(f"SET LOCAL statement_timeout = {settings.sql_timeout_ms}")
                cur = conn.execute(sql)
                cols = [d.name for d in cur.description] if cur.description else []
                rows = [[_jsonable(v) for v in row] for row in cur.fetchall()]
    except Exception as e:  # noqa: BLE001 - surface DB errors safely to the agent
        return SqlResult(sql=sql, columns=[], rows=[], row_count=0,
                         error=f"SQL execution error: {e}")

    return SqlResult(sql=sql, columns=cols, rows=rows, row_count=len(rows))
