"""Vector retrieval over the `documents` table (pgvector, cosine)."""
from __future__ import annotations

from pgvector.psycopg import Vector

from app.core.config import settings
from app.core.db import get_conn
from app.core.llm import embed_query
from app.models import Citation

# `<=>` is pgvector's cosine *distance* (0 = identical). We convert to a
# similarity score (1 - distance) for an intuitive "higher is better" number.
_SEARCH_SQL = """
SELECT source, section, content, 1 - (embedding <=> %s) AS score
FROM documents
ORDER BY embedding <=> %s
LIMIT %s
"""


def search_documents(query: str, top_k: int | None = None) -> list[Citation]:
    top_k = top_k or settings.rag_top_k
    qvec = Vector(embed_query(query))
    with get_conn() as conn:
        rows = conn.execute(_SEARCH_SQL, (qvec, qvec, top_k)).fetchall()

    return [
        Citation(
            source=source,
            section=section,
            snippet=content.strip(),
            score=round(float(score), 4),
        )
        for source, section, content, score in rows
    ]
