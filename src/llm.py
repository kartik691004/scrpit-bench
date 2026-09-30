"""
src/llm.py — LLM transport layer (Google Gemini).

This is the ONLY module in Script Bench that knows which provider is in use.
strategy.py, generator.py and pipeline.py remain provider-independent: they
receive a plain `client` and `model` value and use call_json() below.

JSON mode uses Gemini's native structured output (response_mime_type +
response_json_schema), so the API itself — not just prompt instructions —
constrains responses to schema-conforming JSON. Downstream allowlist
validation and deterministic checks are unchanged.
"""

import os
from typing import Any

from google import genai
from google.genai import types

# Default: flash-lite for free-tier quota headroom (launch-day caps/503s on 3.8).
# Alternative: SCRIPT_BENCH_MODEL=gemini-3.8-flash if your account has paid credits.
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def make_client(api_key: str | None = None) -> genai.Client:
    """Build the Gemini client from an explicit key or the GEMINI_API_KEY env var."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Copy .env.example to .env and add your key "
            "(get one at https://aistudio.google.com/apikey)."
        )
    return genai.Client(api_key=key)


def call_json(
    client: genai.Client,
    model: str,
    prompt: str,
    json_schema: dict[str, Any],
    temperature: float,
) -> str:
    """
    One structured-output LLM call. Returns raw JSON text.

    The schema constrains response SHAPE (and makes invalid-JSON responses
    far rarer than prompt-only conventions); content quality is still judged
    downstream by allowlists (strategy.py) and deterministic validation
    (validator.py) — exactly as before. Provider swap changes nothing about
    the pipeline's guarantees.
    """
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=json_schema,
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=config)
    return (resp.text or "").strip()
