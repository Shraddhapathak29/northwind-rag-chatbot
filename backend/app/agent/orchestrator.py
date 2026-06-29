"""The agentic loop — JSON routing, no native tool-calling.

Two phases per question:
  A) Routing (one non-streamed call): the model returns a small JSON object
     saying which tool(s) to use and with what arguments (or a direct answer for
     greetings / out-of-scope). We parse it ourselves and execute the tools,
     capturing citations (RAG) and the generated SQL + rows. For mixed questions
     the router sets BOTH a search query and an orders question.
  B) Synthesis (one streamed call): a plain completion that writes the grounded
     answer from the tool results, streamed token by token over SSE.

We avoid the provider's native function/tool-calling on purpose: open models via
the Hugging Face router emit tool calls inconsistently and some providers reject
them (`tool_use_failed`). Plain JSON in / plain text out is reliable everywhere.

A single round of tool calls is sufficient for this dataset; multi-step tool
chaining is intentionally out of scope (see README limitations).
"""
from __future__ import annotations

import json
import re
from typing import Iterator, Optional

from app.agent.prompts import ROUTER_PROMPT, SYNTHESIS_PROMPT
from app.core.config import settings
from app.core.llm import chat_extra, client
from app.models import Citation, SqlResult, StreamEvent
from app.rag.retriever import search_documents
from app.sql.text_to_sql import query_orders

FALLBACK = "I don't have that information."


def _parse_router_json(content: str) -> dict:
    """Extract the routing decision from the model's text.

    Tolerant of markdown fences / stray prose: we grab the first {...} block and
    parse it. On any failure we return an empty decision so the caller falls back
    to a safe answer instead of crashing the stream."""
    if not content:
        return {}
    # Strip ```json ... ``` fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        # Otherwise take the first balanced-looking object in the text.
        brace = re.search(r"\{.*\}", content, re.DOTALL)
        raw = brace.group(0) if brace else content
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _clean_str(v) -> Optional[str]:
    """Normalise a JSON field to a non-empty string, or None."""
    if not isinstance(v, str):
        return None
    v = v.strip()
    if not v or v.lower() in {"null", "none"}:
        return None
    return v


def _route(user_message: str) -> dict:
    resp = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        **chat_extra(),
    )
    return _parse_router_json(resp.choices[0].message.content or "")


def run_agent(user_message: str) -> Iterator[StreamEvent]:
    tools_used: list[str] = []
    citations: list[Citation] = []
    sql_result: SqlResult | None = None
    context_blocks: list[str] = []

    # ---- Phase A: routing ----
    decision = _route(user_message)
    search_query = _clean_str(decision.get("search_query"))
    orders_question = _clean_str(decision.get("orders_question"))
    direct_answer = _clean_str(decision.get("direct_answer"))

    # Run RAG if requested.
    if search_query:
        cites = search_documents(search_query)
        tools_used.append("search_documents")
        citations.extend(cites)
        passages = "\n\n".join(
            f"[{c.source} | {c.section}] (score={c.score})\n{c.snippet}" for c in cites
        ) or "No relevant passages found."
        context_blocks.append("DOCUMENT SEARCH RESULTS:\n" + passages)

    # Run text-to-SQL if requested.
    if orders_question:
        result = query_orders(orders_question)
        tools_used.append("query_orders")
        sql_result = result
        if result.error:
            context_blocks.append(f"ORDERS QUERY: failed — {result.error}")
        else:
            preview = [result.columns] + result.rows[:50]
            context_blocks.append(
                f"ORDERS QUERY RESULTS:\nSQL: {result.sql}\n"
                f"Rows ({result.row_count}): {json.dumps(preview, default=str)}"
            )

    # ---- Emit metadata so the UI can show tool / citations / SQL up front ----
    if tools_used:
        yield StreamEvent(type="tools", tools=tools_used)
    if citations:
        yield StreamEvent(type="citations", citations=citations)
    if sql_result is not None:
        yield StreamEvent(type="sql", sql=sql_result)

    # ---- No tool needed: greeting / out-of-scope -> stream the direct answer ----
    if not tools_used:
        answer = direct_answer or FALLBACK
        for word in answer.split(" "):
            yield StreamEvent(type="token", text=word + " ")
        yield StreamEvent(type="done")
        return

    # ---- Phase B: synthesis (plain streamed completion grounded in context) ----
    context = "\n\n".join(context_blocks)
    messages = [
        {"role": "system", "content": SYNTHESIS_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {user_message}\n\n"
                f"Tool results:\n{context}\n\n"
                "Write the final answer for the user now, grounded only in the "
                "tool results above."
            ),
        },
    ]

    stream = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=messages,
        stream=True,
        **chat_extra(),
    )
    got_any = False
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            got_any = True
            yield StreamEvent(type="token", text=delta)

    # Fallback: if streaming produced nothing, retry once non-streamed so the
    # user still gets a grounded answer instead of an empty bubble.
    if not got_any:
        resp = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0,
            messages=messages,
            **chat_extra(),
        )
        text = (resp.choices[0].message.content or "").strip() or FALLBACK
        for word in text.split(" "):
            yield StreamEvent(type="token", text=word + " ")

    yield StreamEvent(type="done")
