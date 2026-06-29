"""Parse policy PDFs -> chunk -> embed -> store in pgvector.

Run as a module:  python -m app.ingest.load_documents /data/documents
"""
from __future__ import annotations

import sys
from pathlib import Path

from pgvector.psycopg import Vector
from pypdf import PdfReader

from app.core.config import settings
from app.core.db import get_conn, init_pool
from app.core.llm import embed_texts
from app.ingest.chunking import chunk_document
from app.ingest.ddl import (
    DOCUMENTS_DDL,
    DOCUMENTS_INDEX,
    DROP_DOCUMENTS,
    ENABLE_PGVECTOR,
)


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_documents(docs_dir: str) -> int:
    pdfs = sorted(Path(docs_dir).glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"no PDFs found in {docs_dir}")

    records: list[tuple[str, str, int, str]] = []  # (source, section, ordinal, content)
    for pdf in pdfs:
        text = _read_pdf(pdf)
        for ch in chunk_document(text, settings.chunk_max_chars, settings.chunk_overlap_chars):
            records.append((pdf.name, ch.section, ch.ordinal, ch.text))

    # Batch-embed all chunk texts in one or few API calls.
    embeddings = embed_texts([r[3] for r in records])

    with get_conn() as conn:
        conn.execute(ENABLE_PGVECTOR)
        # Drop + recreate so the embedding dimension always matches the current
        # model (switching models/providers changes vector size).
        conn.execute(DROP_DOCUMENTS)
        conn.execute(DOCUMENTS_DDL)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO documents (source, section, ordinal, content, embedding)"
                " VALUES (%s, %s, %s, %s, %s)",
                [
                    (src, sec, ordn, content, Vector(emb))
                    for (src, sec, ordn, content), emb in zip(records, embeddings)
                ],
            )
        conn.execute(DOCUMENTS_INDEX)
    return len(records)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/data/documents"
    init_pool()
    n = load_documents(path)
    print(f"[load_documents] embedded + stored {n} chunks from {path}")
