"""
src/cta.py — Contextual CTA style mapping.

Deterministic: pure Python dict, zero LLM calls.
The content_goal (inferred by the strategy stage) drives which CTA style is
instructed during body generation. The LLM writes the CTA text; this module
decides the style intent that shapes tone and action verb.
"""

CONTENT_GOAL_TO_CTA_STYLE: dict[str, str] = {
    "educate": "save",
    "persuade": "follow",
    "entertain": "share_experience",
    "convert": "click",
}

# Human-readable instructions injected into the body/CTA generation prompt.
CTA_STYLE_INSTRUCTIONS: dict[str, str] = {
    "save": (
        "Invite the viewer to save or bookmark this content for future reference. "
        "Be specific about *why* they'll want it again — e.g. the next time they face "
        "the problem you just solved."
    ),
    "follow": (
        "Invite the viewer to follow for more content like this. "
        "Give a specific, concrete reason — name what they'll get, not just 'more great content'."
    ),
    "share_experience": (
        "Ask the viewer a specific question that invites them to share their own experience "
        "in the comments. The question must be directly tied to the topic — not generic."
    ),
    "click": (
        "Direct the viewer to take an action via a link (bio, description, or wherever relevant). "
        "Name exactly what they'll get when they click — a resource, a tool, a next step."
    ),
}


def get_cta_style(content_goal: str) -> str:
    """Map content_goal to CTA style. Raises ValueError on unrecognised goal."""
    style = CONTENT_GOAL_TO_CTA_STYLE.get(content_goal)
    if style is None:
        raise ValueError(
            f"Unknown content_goal: '{content_goal}'. "
            f"Must be one of: {set(CONTENT_GOAL_TO_CTA_STYLE.keys())}"
        )
    return style


def get_cta_instruction(cta_style: str) -> str:
    """Return the generation instruction for a given CTA style."""
    instruction = CTA_STYLE_INSTRUCTIONS.get(cta_style)
    if instruction is None:
        raise ValueError(f"Unknown cta_style: '{cta_style}'.")
    return instruction
