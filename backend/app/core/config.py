"""Central configuration, loaded from environment variables.

Every tunable lives here so the rest of the codebase never reads os.environ
directly. Values come from the process environment (docker-compose / Render)
or a local .env file during development.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM provider (chat completions, OpenAI-compatible) ---
    # Default: Hugging Face Inference Providers router. It is OpenAI-compatible
    # and serves open-source models with token streaming. Put a Hugging Face
    # access token (hf_...) in OPENAI_API_KEY. The OpenAI SDK talks to any
    # compatible API once `openai_base_url` is set; leave base_url empty to use
    # OpenAI itself, or point it at Gemini's endpoint to switch back.
    # Routing uses a JSON decision (not native tool-calling), so any capable
    # instruct model works. Add a ":provider" suffix to pin an HF provider.
    openai_api_key: str = ""
    openai_base_url: str = "https://router.huggingface.co/v1"
    chat_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    # Reasoning-effort toggle. Gemini 2.5 needs "none" to stop empty "thinking"
    # chunks hanging the stream; open HF models (Llama/Qwen) reject the param,
    # so leave this EMPTY for the Hugging Face default.
    reasoning_effort: str = ""

    # --- Embeddings ---
    # Decoupled from the chat provider because open HF chat endpoints do not
    # expose a reliable OpenAI-style /embeddings route.
    #   "local" => fastembed (ONNX, CPU, no API => never rate-limited / 503).
    #   "api"   => OpenAI-compatible /embeddings endpoint, via the chat client
    #              (use this with OpenAI or Gemini; honors `embedding_dim`).
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # 384-dim when provider=local
    embedding_dim: int = 384

    # --- Database ---
    # Standard libpq URL. docker-compose and Render both inject this.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/northwind"

    # --- RAG ---
    rag_top_k: int = 4               # chunks returned per document search
    chunk_max_chars: int = 700       # target chunk size (these docs are tiny)
    chunk_overlap_chars: int = 120

    # --- Text-to-SQL safety ---
    sql_row_limit: int = 200         # hard cap appended to generated SELECTs
    sql_timeout_ms: int = 3000       # per-statement timeout

    # --- Agent ---
    # Business "today" — the assignment fixes this so time-based answers are
    # graded deterministically. Do NOT use the real clock.
    business_today: str = "2026-06-15"

    # --- App ---
    cors_allow_origins: str = "*"    # comma-separated list, or "*"
    company_name: str = "Northwind Gadgets"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
