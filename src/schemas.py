"""
src/schemas.py — JSON schemas for the three structured LLM calls.

These constrain the SHAPE of each response via Gemini's native JSON mode.
Field quality is still enforced downstream: allowlists in strategy.py,
deterministic validation in validator.py. Nothing about the pipeline's
guarantees changes with the provider swap.
"""

STRATEGY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "audience": {"type": "string"},
        "core_insight": {"type": "string"},
        "hook_archetype": {"type": "string"},
        "body_structure": {"type": "string"},
        "content_goal": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "audience",
        "core_insight",
        "hook_archetype",
        "body_structure",
        "content_goal",
    ],
}

HOOK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "rubric_scores": {
                        "type": "object",
                        "properties": {
                            "specificity": {"type": "integer"},
                            "opens_question": {"type": "integer"},
                            "first_five_strength": {"type": "integer"},
                        },
                        "required": [
                            "specificity",
                            "opens_question",
                            "first_five_strength",
                        ],
                    },
                },
                "required": ["text", "rubric_scores"],
            },
        },
    },
    "required": ["candidates"],
}

BODY_CTA_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "body": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["body", "cta"],
}
