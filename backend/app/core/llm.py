"""LLM clients: chat (OpenAI-compatible) + embeddings (pluggable).

Two concerns, deliberately separated:

* **Chat / tool-calling / streaming** go through `client`, an OpenAI-SDK object
  pointed at any OpenAI-compatible endpoint. By default that is Hugging Face's
  Inference Providers router, serving open-source models (e.g. Qwen2.5) with
  tool calling and token streaming. `max_retries` handles transient provider
  5xx ("model is currently experiencing high demand") automatically.

* **Embeddings** are decoupled, because open HF chat endpoints do not expose a
  reliable OpenAI-style `/embeddings` route. With `EMBEDDING_PROVIDER=local`
  (the default) we embed on-box with fastembed (ONNX, CPU) — no API call, so it
  can never be rate-limited or return 503. Set `EMBEDDING_PROVIDER=api` to use
  an OpenAI-compatible embeddings endpoint instead (OpenAI / Gemini).
"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

# Chat client. max_retries>0 so transient 429/5xx from the provider (e.g. HF's
# "high demand" 503) are retried with backoff by the SDK before surfacing.
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url or None,  # None => default OpenAI endpoint
    timeout=60.0,
    max_retries=3,
)


def chat_extra() -> dict:
    """Extra kwargs added to every chat.completions.create call.

    `reasoning_effort` is Gemini-2.5-specific (set it to "none" there to stop
    thinking chunks hanging the stream). Open HF models reject the param, so it
    is empty by default and we return {} — leaving the call untouched."""
    return {"reasoning_effort": settings.reasoning_effort} if settings.reasoning_effort else {}


# --- Embeddings: local (fastembed) ---

@lru_cache(maxsize=1)
def _local_embedder():
    # Imported lazily so the chat-only paths never pay fastembed's import cost,
    # and so `api` deployments don't need the dependency installed.
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=settings.embedding_model)


def _embed_local(texts: list[str]) -> list[list[float]]:
    # fastembed yields numpy arrays; convert to plain lists for psycopg/pgvector.
    return [vec.tolist() for vec in _local_embedder().embed(list(texts))]


# --- Embeddings: OpenAI-compatible API ---

@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=10))
def _embed_api_one(text: str) -> list[float]:
    # `dimensions` pins the vector size to what the `documents` table expects
    # (both OpenAI 3-* and Gemini embedding models honor it).
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dim,
    )
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings (order preserved)."""
    if settings.embedding_provider == "local":
        return _embed_local(texts)
    # Per-text calls keep this compatible with providers whose embeddings
    # endpoint rejects batched list input. The corpus is tiny, so it is cheap.
    return [_embed_api_one(t) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
