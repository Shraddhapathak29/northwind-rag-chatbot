"""SQL safety guard.

Defence in depth around an LLM-generated query:
  1. Strip markdown fences the model sometimes adds.
  2. Parse with sqlparse and require EXACTLY ONE statement.
  3. Require it to be a SELECT (or a WITH ... SELECT CTE).
  4. Reject any DML/DDL/transaction keyword anywhere in the text.
  5. Append a LIMIT if the query has none.

Execution additionally runs on a read-only transaction with a statement
timeout (see runner.py), so even a guard bypass cannot mutate data.
"""
from __future__ import annotations

import re

import sqlparse

from app.core.config import settings

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"comment|copy|merge|call|do|vacuum|analyze|commit|rollback|begin|"
    r"savepoint|set|reset|pg_sleep)\b",
    re.IGNORECASE,
)
_HAS_LIMIT = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)


class UnsafeSQLError(ValueError):
    pass


def sanitize_sql(raw: str) -> str:
    sql = raw.strip()
    # remove ```sql ... ``` fences if present
    sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql, flags=re.IGNORECASE).strip()
    sql = sql.rstrip(";").strip()

    if not sql:
        raise UnsafeSQLError("empty query")

    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise UnsafeSQLError("only a single statement is allowed")

    stmt = statements[0]
    first_kw = stmt.token_first(skip_cm=True)
    keyword = (first_kw.value.lower() if first_kw else "")
    if keyword not in ("select", "with"):
        raise UnsafeSQLError(f"only SELECT queries are allowed (got '{keyword}')")

    if _FORBIDDEN.search(sql):
        raise UnsafeSQLError("query contains a forbidden keyword")

    if not _HAS_LIMIT.search(sql):
        sql = f"{sql}\nLIMIT {settings.sql_row_limit}"

    return sql
