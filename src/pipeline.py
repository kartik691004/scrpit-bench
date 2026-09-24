"""
src/pipeline.py — Orchestrator. Ties all stages together and handles the repair pass.

Execution order:
  1. Compute word budget (deterministic)
  2. Run strategy stage (LLM)
  3. Map content_goal → CTA style (deterministic)
  4. Generate hook candidates, score, select winner (LLM + deterministic scoring)
  5. Generate body + CTA (LLM)
  6. Validate (deterministic)
  7. Repair pass if validation fails — regenerates the single most-offending section,
     then re-validates. One pass max. Raises RepairFailedError if still invalid.

Public output: {hook, body, cta}  (exactly three fields)
Internal state: returned under _insights key; main.py strips it before display.
"""

import os

from openai import OpenAI

from .strategy import run_strategy
from .generator import generate_hook, generate_body_cta
from .validator import validate, WPM
from .cta import get_cta_style, get_cta_instruction

# ── Budget constants ────────────────────────────────────────────────────────────
# Fractions must sum to 1.0.
# Hook gets a disproportionately small but high-impact share.
HOOK_FRACTION: float = 0.20   # 20%
BODY_FRACTION: float = 0.67   # 67%
CTA_FRACTION:  float = 0.13   # 13%

DEFAULT_MODEL = "gpt-4o"


# ── Exceptions ─────────────────────────────────────────────────────────────────
class RepairFailedError(Exception):
    """
    Raised when the single repair pass does not bring the output within tolerance.

    Carries the validation errors and the best-effort output so the caller can
    decide whether to surface the output with a warning or hard-fail.
    """
    def __init__(self, errors: list[str], output: dict):
        super().__init__(f"Repair pass did not resolve: {errors}")
        self.errors = errors
        self.output = output


# ── Pipeline class ─────────────────────────────────────────────────────────────
class Pipeline:
    """
    Stateless pipeline runner. One instance per process; call .run() multiple times.

    Args:
        model:   OpenAI model ID (default: gpt-4o).
        api_key: Override OPENAI_API_KEY env var (useful for testing).
    """

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        self.client = OpenAI(api_key=key)
        self.model = model

    # ── Budget ─────────────────────────────────────────────────────────────────
    def _compute_budget(self, target_seconds: int) -> dict:
        """
        Allocate word budget across sections from target runtime.

        Formula: total_words = round((target_seconds / 60) * WPM)
        WPM = 140 (constant from validator.py, documented as an approximation).
        """
        total = round((target_seconds / 60) * WPM)
        hook_words = round(total * HOOK_FRACTION)
        cta_words  = round(total * CTA_FRACTION)
        body_words = total - hook_words - cta_words  # avoids rounding drift
        return {
            "total_words": total,
            "hook_words":  hook_words,
            "body_words":  body_words,
            "cta_words":   cta_words,
        }

    # ── Main run ───────────────────────────────────────────────────────────────
    def run(self, niche: str, topic: str, target_seconds: int) -> dict:
        """
        Run the full pipeline and return the result.

        Public output fields: hook, body, cta.
        Internal field: _insights (stripped by main.py before display).

        Raises:
            strategy.ParseError       if the LLM returns unparseable JSON
            strategy.ValidationError  if the LLM returns an invalid archetype/structure
            generator.ParseError      if generation responses are unparseable
            RepairFailedError         if the repair pass doesn't resolve validation
        """
        # ── 1. Budget ──────────────────────────────────────────────────────────
        budget = self._compute_budget(target_seconds)

        # ── 2. Strategy ────────────────────────────────────────────────────────
        strategy = run_strategy(niche, topic, self.client, self.model)

        # ── 3. CTA style (deterministic mapping) ──────────────────────────────
        cta_style       = get_cta_style(strategy["content_goal"])
        cta_instruction = get_cta_instruction(cta_style)

        # ── 4. Hook generation + scoring ───────────────────────────────────────
        hook_text, hook_candidates = generate_hook(
            niche=niche,
            topic=topic,
            audience=strategy["audience"],
            core_insight=strategy["core_insight"],
            hook_archetype=strategy["hook_archetype"],
            hook_words=budget["hook_words"],
            client=self.client,
            model=self.model,
        )

        # ── 5. Body + CTA generation ───────────────────────────────────────────
        body_text, cta_text = generate_body_cta(
            niche=niche,
            topic=topic,
            audience=strategy["audience"],
            core_insight=strategy["core_insight"],
            hook=hook_text,
            body_structure=strategy["body_structure"],
            cta_style=cta_style,
            cta_instruction=cta_instruction,
            body_words=budget["body_words"],
            cta_words=budget["cta_words"],
            client=self.client,
            model=self.model,
        )

        output = {"hook": hook_text, "body": body_text, "cta": cta_text}

        # ── 6. Validate ────────────────────────────────────────────────────────
        validation = validate(output, target_seconds, budget)
        _repaired = False

        # ── 7. Repair pass (at most once) ──────────────────────────────────────
        if not validation.passed and validation.offending_sections:
            _repaired = True
            offending = validation.offending_sections[0]

            if offending == "hook":
                hook_text, hook_candidates = generate_hook(
                    niche=niche,
                    topic=topic,
                    audience=strategy["audience"],
                    core_insight=strategy["core_insight"],
                    hook_archetype=strategy["hook_archetype"],
                    hook_words=budget["hook_words"],
                    client=self.client,
                    model=self.model,
                )
                output["hook"] = hook_text

            elif offending in ("body", "cta"):
                # Body and CTA are generated together — repair both
                body_text, cta_text = generate_body_cta(
                    niche=niche,
                    topic=topic,
                    audience=strategy["audience"],
                    core_insight=strategy["core_insight"],
                    hook=output["hook"],
                    body_structure=strategy["body_structure"],
                    cta_style=cta_style,
                    cta_instruction=cta_instruction,
                    body_words=budget["body_words"],
                    cta_words=budget["cta_words"],
                    client=self.client,
                    model=self.model,
                )
                output["body"] = body_text
                output["cta"] = cta_text

            # Re-validate after repair
            validation = validate(output, target_seconds, budget)
            if not validation.passed:
                raise RepairFailedError(errors=validation.errors, output=output)

        # ── Assemble result ────────────────────────────────────────────────────
        word_counts = {
            "hook":  len(output["hook"].split()),
            "body":  len(output["body"].split()),
            "cta":   len(output["cta"].split()),
        }
        word_counts["total"] = sum(word_counts.values())
        estimated_secs = word_counts["total"] / WPM * 60

        return {
            **output,
            "_insights": {
                "strategy":          strategy,
                "cta_style":         cta_style,
                "budget":            budget,
                "hook_candidates":   hook_candidates,
                "repaired":          _repaired,
                "word_counts":       word_counts,
                "estimated_seconds": round(estimated_secs, 1),
                "target_seconds":    target_seconds,
                "validation_passed": validation.passed,
            },
        }
