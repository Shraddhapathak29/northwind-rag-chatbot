"""Section-aware chunking for the policy PDFs.

These documents are short and cleanly structured into headed sections
(e.g. "1. Return Window", "Shipping and Delivery"). We split on those
headings so each chunk carries a meaningful `section` label that becomes a
human-readable citation. Long sections are further split with overlap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A heading is either a numbered clause ("1. Return Window") or a short
# title-case line with no terminal punctuation ("Shipping and Delivery").
_NUMBERED = re.compile(r"^\s*\d+\.\s+[A-Z].*$")
_TITLE = re.compile(r"^[A-Z][A-Za-z0-9 ,&/'-]{2,60}$")


@dataclass
class Chunk:
    section: str
    text: str
    ordinal: int


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or s.endswith((".", ":", ",")):
        # numbered clauses are allowed to "end" with their own number dot,
        # but a normal sentence ending in '.' is not a heading.
        if _NUMBERED.match(s):
            return True
        return False
    if _NUMBERED.match(s):
        return True
    # Title-case heading: most words capitalised, few words, no sentence verb-y length.
    if _TITLE.match(s) and len(s.split()) <= 6:
        return True
    return False


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(section_title, body), ...] preserving document order."""
    lines = [ln for ln in text.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    current_title = "Overview"
    current_body: list[str] = []

    for ln in lines:
        if _is_heading(ln):
            if current_body:
                sections.append((current_title, current_body))
            current_title = ln.strip()
            current_body = []
        elif ln.strip():
            current_body.append(ln.strip())
    if current_body:
        sections.append((current_title, current_body))

    return [(t, " ".join(b)) for t, b in sections if b]


def _window(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = start + max_chars
        # try to break on a sentence boundary near the window edge
        slice_ = text[start:end]
        dot = slice_.rfind(". ")
        if dot > max_chars * 0.5 and end < len(text):
            end = start + dot + 1
        out.append(text[start:end].strip())
        start = max(end - overlap, end) if end >= len(text) else end - overlap
    return [c for c in out if c]


def chunk_document(full_text: str, max_chars: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    ordinal = 0
    for title, body in _split_sections(full_text):
        for piece in _window(body, max_chars, overlap):
            # Prefix the section so the embedding has topical context.
            chunks.append(Chunk(section=title, text=f"{title}\n{piece}", ordinal=ordinal))
            ordinal += 1
    return chunks
