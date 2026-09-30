"""
src/strategy.py — Stage 1: Strategy.

Calls the LLM once to infer:
  - audience      : who is watching this content
  - core_insight  : the sharpest specific thing to communicate
  - hook_archetype: one of the five named archetypes
  - body_structure: one of the three named structures
  - content_goal  : one of the four named goals (drives CTA style downstream)
  - reasoning     : brief explanation of the choices (logged, never public)

All choices are validated against explicit allowlists — the pipeline fails fast
if the model returns a value not in the enum, rather than silently proceeding
with a bad archetype.

Provider note: the call goes through src/llm.py (the only provider-aware
module) using Gemini's native JSON mode with the STRATEGY_SCHEMA shape
constraint. This module contains no provider code.
"""

import json
from pathlib import Path

from .llm import call_json
from .schemas import STRATEGY_SCHEMA
from .utils import fill_prompt

# ── Allowlists (single source of truth) ───────────────────────────────────────
ALLOWED_HOOK_ARCHETYPES: frozenset[str] = frozenset({
    "curiosity_gap",
    "bold_claim",
    "pattern_interrupt",
    "direct_question",
    "story",
})

ALLOWED_BODY_STRUCTURES: frozenset[str] = frozenset({
    "problem_agitate_solve",
    "before_after_bridge",
    "story_arc",
})

ALLOWED_CONTENT_GOALS: frozenset[str] = frozenset({
    "educate",
    "persuade",
    "entertain",
    "convert",
})

PROMPT_PATH = Path(__file__).parent / "prompts" / "strategy.txt"


# ── Exceptions ─────────────────────────────────────────────────────────────────
class ParseError(Exception):
    """Raised when the LLM response cannot be parsed into the expected structure."""


class ValidationError(Exception):
    """Raised when a parsed value falls outside the allowed enum."""


# ── Parsing ────────────────────────────────────────────────────────────────────
def _parse_json(raw: str) -> dict:
    """Parse a JSON response. Raises ParseError on invalid JSON."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"Strategy response is not valid JSON: {exc}\n"
            f"Raw (first 400 chars):\n{raw[:400]}"
        ) from exc


def _validate_strategy(data: dict) -> dict:
    """Validate parsed strategy dict against allowlists. Returns cleaned dict."""
    required = {"audience", "core_insight", "hook_archetype", "body_structure", "content_goal"}
    missing = required - data.keys()
    if missing:
        raise ParseError(f"Strategy response missing required fields: {missing}")

    arch = data["hook_archetype"]
    if arch not in ALLOWED_HOOK_ARCHETYPES:
        raise ValidationError(
            f"Invalid hook_archetype '{arch}'. "
            f"Must be one of: {sorted(ALLOWED_HOOK_ARCHETYPES)}"
        )

    struct = data["body_structure"]
    if struct not in ALLOWED_BODY_STRUCTURES:
        raise ValidationError(
            f"Invalid body_structure '{struct}'. "
            f"Must be one of: {sorted(ALLOWED_BODY_STRUCTURES)}"
        )

    goal = data["content_goal"]
    if goal not in ALLOWED_CONTENT_GOALS:
        raise ValidationError(
            f"Invalid content_goal '{goal}'. "
            f"Must be one of: {sorted(ALLOWED_CONTENT_GOALS)}"
        )

    return {
        "audience":       str(data["audience"]).strip(),
        "core_insight":   str(data["core_insight"]).strip(),
        "hook_archetype": arch,
        "body_structure": struct,
        "content_goal":   goal,
        "reasoning":      str(data.get("reasoning", "")).strip(),
    }


# ── Public API ─────────────────────────────────────────────────────────────────
def run_strategy(niche: str, topic: str, client, model: str) -> dict:
    """
    Run the strategy stage.

    Makes one structured-output LLM call (with one retry on JSON parse
    failure) and returns a validated strategy dict.

    Args:
        niche:  Content niche string, e.g. "personal finance".
        topic:  One-sentence topic string.
        client: Transport client from src.llm.make_client().
        model:  Model ID string.

    Returns:
        Dict with keys: audience, core_insight, hook_archetype,
                        body_structure, content_goal, reasoning.
    """
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = fill_prompt(template, niche=niche, topic=topic)

    raw = call_json(client, model, prompt, STRATEGY_SCHEMA, temperature=0.6)

    try:
        data = _parse_json(raw)
    except ParseError:
        # One retry — native JSON mode makes this rare, but keep the guarantee.
        retry_prompt = (
            prompt
            + "\n\nYour previous response was not valid JSON. "
            "Respond ONLY with the JSON object."
        )
        raw = call_json(client, model, retry_prompt, STRATEGY_SCHEMA, temperature=0.6)
        data = _parse_json(raw)  # let it raise if it fails again

    return _validate_strategy(data)
