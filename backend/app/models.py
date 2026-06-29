"""API request/response and internal event schemas."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class Citation(BaseModel):
    source: str          # document filename, e.g. "returns_policy.pdf"
    section: str         # human-readable section/heading
    snippet: str         # the chunk text used
    score: float         # cosine similarity (higher = closer)


class SqlResult(BaseModel):
    sql: str                       # the SQL actually executed
    columns: list[str]
    rows: list[list]               # JSON-safe row values
    row_count: int
    error: Optional[str] = None    # populated if generation/exec failed safely


# --- Streaming event envelope (one JSON object per SSE "data:" line) ---
StreamEventType = Literal["tools", "citations", "sql", "token", "done", "error"]


class StreamEvent(BaseModel):
    type: StreamEventType
    # Only the field relevant to `type` is set.
    tools: Optional[list[str]] = None
    citations: Optional[list[Citation]] = None
    sql: Optional[SqlResult] = None
    text: Optional[str] = None
