"""
src/utils.py — Shared prompt-rendering utility.

Prompts use <VARIABLE_NAME> placeholders (angle-bracket style).
This avoids collisions with JSON braces that appear inside prompt examples.
"""


def fill_prompt(template: str, **kwargs) -> str:
    """
    Fill a prompt template by replacing <KEY> with its value.

    Example:
        fill_prompt("Hello <NAME>!", NAME="world") -> "Hello world!"

    Keys are matched case-insensitively: both `niche` and `NICHE` become <NICHE>.
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"<{key.upper()}>", str(value))
    return result
