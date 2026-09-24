"""
src/validator.py — Deterministic validation. Zero LLM calls.

Three checks:
  1. Required fields — hook, body, cta all present and non-empty.
  2. Boilerplate CTA guard — rejects known generic phrases.
  3. Runtime tolerance — total estimated seconds within ±10% of target.

estimate_seconds() uses a fixed WPM constant (140), documented as an approximation
of spoken pace. The same constant drives the budget allocation in pipeline.py,
ensuring internal consistency even though individual speakers vary.
"""

from dataclasses import dataclass, field

# ── Constants ──────────────────────────────────────────────────────────────────
WPM = 140  # spoken words per minute — midpoint of 130–150 wpm range

# Phrases that indicate a generic, non-contextual CTA.
# Lowercase; compared against a lowercased CTA via substring match.
BOILERPLATE_PHRASES: frozenset[str] = frozenset({
    "like and subscribe",
    "don't forget to like",
    "hit the bell",
    "smash the like",
    "follow for more",
    "subscribe for more",
    "give this video a like",
    "tap the subscribe",
    "turn on notifications",
    "comment below if you",   # too generic
    "drop a like",
    "share this video",
})


# ── Data types ─────────────────────────────────────────────────────────────────
@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    offending_sections: list[str] = field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────────
def estimate_seconds(text: str) -> float:
    """
    Estimate how long `text` takes to speak aloud.

    Formula: word_count / WPM * 60
    WPM=140 is a documented approximation; actual pace varies ±15–20% by speaker.
    """
    return len(text.split()) / WPM * 60


# ── Individual checks ──────────────────────────────────────────────────────────
def check_required_fields(output: dict) -> list[str]:
    """Return a list of error strings for missing or empty required fields."""
    errors: list[str] = []
    for field_name in ("hook", "body", "cta"):
        if field_name not in output:
            errors.append(f"Missing required field: '{field_name}'")
        elif not str(output[field_name]).strip():
            errors.append(f"Field '{field_name}' is present but empty")
    return errors


def check_no_boilerplate_cta(cta: str) -> list[str]:
    """Return a list of error strings for boilerplate phrases found in the CTA."""
    errors: list[str] = []
    cta_lower = cta.lower()
    for phrase in BOILERPLATE_PHRASES:
        if phrase in cta_lower:
            errors.append(f"CTA contains boilerplate phrase: '{phrase}'")
    return errors


def check_runtime_tolerance(
    output: dict,
    budget: dict,
    target_seconds: int,
    tolerance: float = 0.10,
) -> tuple[list[str], list[str]]:
    """
    Check that total estimated runtime is within `tolerance` of `target_seconds`.

    Returns (errors, offending_sections).
    offending_sections contains the section with the largest absolute deviation
    from its word-budget allocation — used by the repair pass to target the right section.
    """
    errors: list[str] = []
    offending: list[str] = []

    hook_secs = estimate_seconds(output.get("hook", ""))
    body_secs = estimate_seconds(output.get("body", ""))
    cta_secs = estimate_seconds(output.get("cta", ""))
    total_secs = hook_secs + body_secs + cta_secs

    lower = target_seconds * (1 - tolerance)
    upper = target_seconds * (1 + tolerance)

    if not (lower <= total_secs <= upper):
        errors.append(
            f"Total runtime {total_secs:.1f}s is outside the ±10% tolerance "
            f"[{lower:.1f}s – {upper:.1f}s] for target {target_seconds}s"
        )
        # Identify the section deviating most from its budget allocation
        budget_secs = {
            "hook": budget["hook_words"] / WPM * 60,
            "body": budget["body_words"] / WPM * 60,
            "cta":  budget["cta_words"]  / WPM * 60,
        }
        actual_secs = {"hook": hook_secs, "body": body_secs, "cta": cta_secs}
        deviations = {s: abs(actual_secs[s] - budget_secs[s]) for s in budget_secs}
        worst = max(deviations, key=lambda s: deviations[s])
        offending.append(worst)

    return errors, offending


# ── Main entry point ───────────────────────────────────────────────────────────
def validate(
    output: dict,
    target_seconds: int,
    budget: dict,
    tolerance: float = 0.10,
) -> ValidationResult:
    """
    Run all three checks against the pipeline output.

    Args:
        output:         Dict with keys 'hook', 'body', 'cta'.
        target_seconds: Intended runtime in seconds.
        budget:         Word budget dict from pipeline._compute_budget().
        tolerance:      Allowed deviation fraction (default 0.10 = ±10%).

    Returns:
        ValidationResult with passed flag, error messages, and offending sections.
    """
    all_errors: list[str] = []
    offending_sections: list[str] = []

    # Check 1: required fields
    field_errors = check_required_fields(output)
    all_errors.extend(field_errors)

    # Check 2: boilerplate CTA (skip if CTA is missing — already caught above)
    if "cta" in output and output["cta"].strip():
        bp_errors = check_no_boilerplate_cta(output["cta"])
        all_errors.extend(bp_errors)
        if bp_errors and "cta" not in offending_sections:
            offending_sections.append("cta")

    # Check 3: runtime tolerance (skip if fields are broken — counts would be misleading)
    if not field_errors:
        rt_errors, rt_offending = check_runtime_tolerance(
            output, budget, target_seconds, tolerance
        )
        all_errors.extend(rt_errors)
        for section in rt_offending:
            if section not in offending_sections:
                offending_sections.append(section)

    return ValidationResult(
        passed=len(all_errors) == 0,
        errors=all_errors,
        offending_sections=offending_sections,
    )
