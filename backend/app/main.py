"""FastAPI entrypoint: health, schema introspection, and the streaming chat API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.agent.orchestrator import run_agent
from app.core.config import settings
from app.core.db import close_pool, get_conn, init_pool
from app.models import ChatRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(title="Northwind Dual-Mode Agentic RAG", version="1.0.0", lifespan=lifespan)

origins = (
    ["*"] if settings.cors_allow_origins.strip() == "*"
    else [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness + quick data sanity check (row counts)."""
    out = {"status": "ok"}
    try:
        with get_conn() as conn:
            out["orders"] = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
            out["doc_chunks"] = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
    except Exception as e:  # noqa: BLE001
        out["status"] = "degraded"
        out["error"] = str(e)
    return out


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Token-level streaming chat. Emits Server-Sent Events; each `data:` line is
    a JSON StreamEvent: {type: tools|citations|sql|token|done|error, ...}."""

    def event_generator():
        try:
            for event in run_agent(req.message):
                yield {"data": event.model_dump_json(exclude_none=True)}
        except Exception as e:  # noqa: BLE001 - never leak a raw 500 mid-stream
            # Print the full traceback to the server logs so failures are
            # debuggable (the client only ever sees a short error message).
            import traceback
            traceback.print_exc()
            yield {"data": f'{{"type":"error","text":{_json_str(str(e))}}}'}

    return EventSourceResponse(event_generator())


def _json_str(s: str) -> str:
    import json
    return json.dumps(s)
