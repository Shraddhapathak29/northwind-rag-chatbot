"""Unit tests that need neither a database nor the OpenAI API.

Run: cd backend && PYTHONPATH=. OPENAI_API_KEY=test python -m pytest -q
"""
import pytest

from app.ingest.chunking import chunk_document
from app.sql.guard import UnsafeSQLError, sanitize_sql

SAMPLE = """Northwind Gadgets — Returns Policy
1. Return Window
Customers may return any eligible product within 30 days of delivery.
2. Eligibility
Items must be unused and in original packaging.
"""


def test_chunker_splits_on_sections():
    chunks = chunk_document(SAMPLE, max_chars=700, overlap=120)
    sections = {c.section for c in chunks}
    assert "1. Return Window" in sections
    assert "2. Eligibility" in sections
    # each chunk text is prefixed with its section for embedding context
    assert all(c.text.startswith(c.section) for c in chunks)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM orders WHERE status='pending'",
        "select sum(amount) from orders",
        "```sql\nSELECT * FROM orders LIMIT 5\n```",
        "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
    ],
)
def test_guard_accepts_selects(sql):
    out = sanitize_sql(sql)
    assert out.lower().startswith(("select", "with"))
    assert "limit" in out.lower()  # auto-appended when missing


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "UPDATE orders SET amount=0",
        "DROP TABLE orders",
        "SELECT 1; DROP TABLE orders",
        "SELECT * FROM orders; SELECT * FROM documents",
        "",
    ],
)
def test_guard_rejects_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        sanitize_sql(sql)
