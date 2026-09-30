"""
src/generator.py — Stages 2 & 3: Hook selection and body/CTA generation.

Stage 2 — Hook selection:
  The LLM generates 3 candidates for the chosen archetype, each with rubric scores
  for specificity, opens_question, and first_five_strength (all integers 1–5).
  The winner is chosen by a DETERMINISTIC weighted sum in Python — the model
  provides data; Python makes the decision. Runner-up candidates and their scores
  are stored in the _insights field (internal only, never public output).

Stage 3 — Body + CTA generation:
  A single LLM call writes the body and CTA together, given the chosen hook,
  body structure, word budget, and CTA style instruction.

Both stages use one retry on JSON parse failure.

Provider note: calls go through src/llm.py (the only provider-aware module)
using Gemini's native JSON mode with the HOOK_SCHEMA / BODY_CTA_SCHEMA shape
constraints. This module contains no provider code.
"""

import json
from pathlib import Path

from .llm import call_json
from .schemas import BODY_CTA_SCHEMA, HOOK_SCHEMA
from .utils import fill_prompt

# ── Prompt paths ───────────────────────────────────────────────────────────────
HOOK_PROMPT_PATH = Path(__file__).parent / "prompts" / "hook_candidates.txt"
BODY_PROMPT_PATH = Path(__file__).parent / "prompts" / "body_cta.txt"

# ── Rubric weights (deterministic scoring in Python) ──────────────────────────
RUBRIC_WEIGHTS: dict[str, float] = {
    "specificity":        0.35,
    "opens_question":     0.40,
    "first_five_strength": 0.25,
}

# ── Archetype / structure descriptions injected into prompts ──────────────────
ARCHETYPE_DESCRIPTIONS: dict[str, str] = {
    "curiosity_gap": (
        "Tease a surprising result without revealing it. "
        "Create an information gap the viewer must fill by watching on."
    ),
    "bold_claim": (
        "Open with a confident, counterintuitive, or provocative statement of fact or opinion. "
        "It should feel slightly uncomfortable to ignore."
    ),
    "pattern_interrupt": (
        "Subvert an expectation. Start with something that breaks the viewer's existing mental pattern — "
        "a contradiction, an unusual juxtaposition, or an unexpected reversal."
    ),
    "direct_question": (
        "Ask a specific, sharp question the audience has secretly been asking themselves. "
        "Not 'have you ever wondered' — something precise and personal."
    ),
    "story": (
        "Open mid-action in a relatable scene. Immediate, concrete, first- or second-person. "
        "Drop the viewer into a moment, not a setup."
    ),
}

STRUCTURE_DESCRIPTIONS: dict[str, str] = {
    "problem_agitate_solve": (
        "First, name the problem the hook implied. "
        "Then agitate it — make it feel urgent, real, and personal. "
        "Then deliver the solution cleanly and specifically."
    ),
    "before_after_bridge": (
        "Paint the 'before' state the audience knows and lives in. "
        "Paint the 'after' state they want. "
        "Bridge with the specific mechanism that creates the change."
    ),
    "story_arc": (
        "Set up a situation the viewer recognises. "
        "Build to a moment of change or realisation. "
        "Land on a clean, concrete takeaway. Keep every beat tight."
    ),
}


# ── Exceptions ─────────────────────────────────────────────────────────────────
class ParseError(Exception):
    """Raised when the LLM response cannot be parsed into the expected structure."""


# ── Scoring ────────────────────────────────────────────────────────────────────
def _score_candidate(candidate: dict) -> float:
    """Deterministic weighted sum of rubric scores. Higher is better."""
    scores = candidate.get("rubric_scores", {})
    return sum(
        float(scores.get(dim, 0)) * weight
        for dim, weight in RUBRIC_WEIGHTS.items()
    )


# ── JSON parsing ───────────────────────────────────────────────────────────────
def _parse_json(raw: str) -> dict:
    """Parse a JSON response. Raises ParseError on invalid JSON."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"Response is not valid JSON: {exc}\n"
            f"Raw (first 400 chars):\n{raw[:400]}"
        ) from exc


def _call_with_retry(
    client,
    model: str,
    prompt: str,
    json_schema: dict,
    temperature: float,
) -> dict:
    """One structured-output call + parse. One retry on parse failure."""
    raw = call_json(client, model, prompt, json_schema, temperature)
    try:
        return _parse_json(raw)
    except ParseError:
        retry_prompt = (
            prompt
            + "\n\nYour previous response was not valid JSON. "
            "Respond ONLY with the JSON object."
        )
        return _parse_json(call_json(client, model, retry_prompt, json_schema, temperature))


# ── Stage 2: Hook selection ────────────────────────────────────────────────────
def generate_hook(
    niche: str,
    topic: str,
    audience: str,
    core_insight: str,
    hook_archetype: str,
    hook_words: int,
    client,
    model: str,
) -> tuple[str, list[dict]]:
    """
    Generate 3 hook candidates, score them deterministically, return the winner.

    Returns:
        (winner_text, all_candidates)
        all_candidates includes _score for each candidate (internal use only).
    """
    template = HOOK_PROMPT_PATH.read_text(encoding="utf-8")
    archetype_desc = ARCHETYPE_DESCRIPTIONS.get(hook_archetype, "")
    hook_min = max(1, round(hook_words * 0.85))
    hook_max = round(hook_words * 1.15)

    prompt = fill_prompt(
        template,
        niche=niche,
        topic=topic,
        audience=audience,
        core_insight=core_insight,
        hook_archetype=hook_archetype,
        hook_words=hook_words,
        hook_min=hook_min,
        hook_max=hook_max,
        archetype_description=archetype_desc,
    )

    data = _call_with_retry(client, model, prompt, HOOK_SCHEMA, temperature=0.85)
    candidates: list[dict] = data.get("candidates", [])

    if not candidates:
        raise ParseError("Hook response contained no candidates.")

    # Deterministic scoring in Python — model provided data, Python decides winner
    for c in candidates:
        c["_score"] = round(_score_candidate(c), 4)

    winner = max(candidates, key=lambda c: c["_score"])
    return winner["text"].strip(), candidates


# ── Stage 3: Body + CTA generation ────────────────────────────────────────────
def generate_body_cta(
    niche: str,
    topic: str,
    audience: str,
    core_insight: str,
    hook: str,
    body_structure: str,
    cta_style: str,
    cta_instruction: str,
    body_words: int,
    cta_words: int,
    client,
    model: str,
) -> tuple[str, str]:
    """
    Generate body and CTA in a single LLM call.

    Returns:
        (body_text, cta_text)
    """
    template = BODY_PROMPT_PATH.read_text(encoding="utf-8")
    structure_desc = STRUCTURE_DESCRIPTIONS.get(body_structure, "")

    tolerance = 0.12  # slightly looser budget for the prompt itself;
    body_min = max(1, round(body_words * (1 - tolerance)))
    body_max = round(body_words * (1 + tolerance))
    cta_min = max(1, round(cta_words * (1 - tolerance)))
    cta_max = round(cta_words * (1 + tolerance))

    prompt = fill_prompt(
        template,
        niche=niche,
        topic=topic,
        audience=audience,
        core_insight=core_insight,
        hook=hook,
        body_structure=body_structure,
        body_structure_description=structure_desc,
        cta_style=cta_style,
        cta_instruction=cta_instruction,
        body_words=body_words,
        body_min=body_min,
        body_max=body_max,
        cta_words=cta_words,
        cta_min=cta_min,
        cta_max=cta_max,
    )

    data = _call_with_retry(client, model, prompt, BODY_CTA_SCHEMA, temperature=0.80)

    body = str(data.get("body", "")).strip()
    cta = str(data.get("cta", "")).strip()

    if not body:
        raise ParseError("Body generation returned an empty body.")
    if not cta:
        raise ParseError("Body generation returned an empty CTA.")

    return body, cta
