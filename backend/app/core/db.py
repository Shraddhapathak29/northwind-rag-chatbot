"""PostgreSQL connection pool + pgvector registration.

A single psycopg ConnectionPool is shared across the app. pgvector's adapter
is registered on every new connection so Python lists/np arrays map to the
`vector` type transparently.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from app.core.config import settings


def _configure(conn: psycopg.Connection) -> None:
    # The pgvector adapter can only be registered once the `vector` type exists,
    # so ensure the extension is created before registering (idempotent; runs on
    # every new pooled connection but CREATE EXTENSION IF NOT EXISTS is a no-op
    # after the first). Without this, the very first boot fails with
    # "vector type not found in the database" because the pool opens before
    # ingest has had a chance to create the extension.
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)


# min_size=1 keeps a warm connection; open lazily so import never blocks.
pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    configure=_configure,
    open=False,
    kwargs={"autocommit": True},
)


def init_pool() -> None:
    if pool.closed:
        pool.open()
    pool.wait(timeout=30.0)


def close_pool() -> None:
    if not pool.closed:
        pool.close()


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with pool.connection() as conn:
        yield conn
