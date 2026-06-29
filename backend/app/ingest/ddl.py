"""Database schema (DDL). Idempotent: safe to run on every ingest."""
from __future__ import annotations

from app.core.config import settings

ENABLE_PGVECTOR = "CREATE EXTENSION IF NOT EXISTS vector;"

# Structured knowledge — queried by the text-to-SQL tool.
ORDERS_DDL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    customer    TEXT NOT NULL,
    product     TEXT NOT NULL,
    amount      INTEGER NOT NULL,        -- whole Indian Rupees
    status      TEXT NOT NULL,           -- pending|processing|shipped|delivered|cancelled|returned
    order_date  DATE NOT NULL
);
"""

# Unstructured knowledge — embedded for vector RAG.
DOCUMENTS_DDL = f"""
CREATE TABLE IF NOT EXISTS documents (
    id         BIGSERIAL PRIMARY KEY,
    source     TEXT NOT NULL,            -- filename, used as citation source
    section    TEXT NOT NULL,            -- heading within the document
    ordinal    INTEGER NOT NULL,         -- chunk order within the document
    content    TEXT NOT NULL,
    embedding  vector({settings.embedding_dim}) NOT NULL
);
"""

# IVFFlat index for cosine distance. For ~30 chunks this is overkill but it is
# the production-correct choice and demonstrates the right pattern.
DOCUMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
"""

# Dropped (not truncated) before re-ingest: the embedding column's dimension is
# baked into the table definition, so switching embedding models/dims requires
# recreating the table rather than just clearing its rows.
DROP_DOCUMENTS = "DROP TABLE IF EXISTS documents;"

TRUNCATE_ORDERS = "TRUNCATE orders;"
