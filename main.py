#!/usr/bin/env python3
"""
main.py — Script Bench CLI entry point.

Usage:
    python main.py --niche "personal finance" --topic "why savings accounts lose money" --seconds 60
    python main.py --niche "fitness" --topic "the warm-up mistake" --seconds 45 --insights
    python main.py --niche "cooking" --topic "restaurant pasta secret" --seconds 45 --model gpt-4o-mini

Public output is always printed as a clean JSON block: {hook, body, cta}.
Pass --insights to also print the internal reasoning sidecar.
"""

import json
import sys

import typer
from dotenv import load_dotenv

from src.pipeline import Pipeline, RepairFailedError
from src.strategy import ParseError as StrategyParseError, ValidationError as StrategyValidationError
from src.generator import ParseError as GeneratorParseError
from src.validator import ValidationResult

load_dotenv()  # loads .env if present; no-op if absent

app = typer.Typer(
    help="Script Bench — generate short-form video scripts with a 5-stage pipeline.",
    add_completion=False,
)


@app.command()
def generate(
    niche: str = typer.Option(
        ...,
        "--niche",
        help="Content niche, e.g. 'personal finance' or 'fitness'.",
    ),
    topic: str = typer.Option(
        ...,
        "--topic",
        help="One-sentence topic, e.g. 'why your savings account is losing you money'.",
    ),
    seconds: int = typer.Option(
        ...,
        "--seconds",
        help="Target runtime in seconds. Typical values: 30, 45, 60.",
        min=15,
        max=120,
    ),
    model: str = typer.Option(
        "gpt-4o",
        "--model",
        help="OpenAI model to use (default: gpt-4o).",
    ),
    insights: bool = typer.Option(
        False,
        "--insights",
        help="Also print internal reasoning (strategy, hook scores, word budget).",
    ),
    save_insights: bool = typer.Option(
        False,
        "--save-insights",
        help="Save internal reasoning to <niche>_<seconds>s_insights.json alongside output.",
    ),
) -> None:
    """Generate a short-form video script: hook, body, cta."""

    typer.echo(f"Running pipeline: niche='{niche}' | topic='{topic}' | {seconds}s | model={model}", err=True)
    typer.echo("", err=True)

    pipeline = Pipeline(model=model)

    try:
        result = pipeline.run(niche=niche, topic=topic, target_seconds=seconds)
    except RepairFailedError as exc:
        typer.echo("⚠  Repair pass failed — returning best-effort output with warnings.", err=True)
        for err in exc.errors:
            typer.echo(f"   Validation error: {err}", err=True)
        public = {k: v for k, v in exc.output.items() if not k.startswith("_")}
        typer.echo(json.dumps(public, indent=2, ensure_ascii=False))
        sys.exit(1)
    except (StrategyParseError, StrategyValidationError, GeneratorParseError) as exc:
        typer.echo(f"✗  Pipeline error: {exc}", err=True)
        sys.exit(2)

    # ── Public output ──────────────────────────────────────────────────────────
    public_output = {
        "hook": result["hook"],
        "body": result["body"],
        "cta":  result["cta"],
    }
    typer.echo(json.dumps(public_output, indent=2, ensure_ascii=False))

    # ── Internal insights (optional display) ───────────────────────────────────
    internal = result.get("_insights", {})
    if insights:
        typer.echo("\n--- Internal Insights ---", err=False)
        typer.echo(json.dumps(internal, indent=2, ensure_ascii=False))

    # ── Save insights to file (optional) ──────────────────────────────────────
    if save_insights:
        slug = niche.lower().replace(" ", "_")[:20]
        filename = f"{slug}_{seconds}s_insights.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(internal, f, indent=2, ensure_ascii=False)
        typer.echo(f"\nInsights saved to {filename}", err=True)

    # ── Runtime summary (always to stderr) ────────────────────────────────────
    typer.echo("", err=True)
    typer.echo(
        f"✓  Done | estimated {internal.get('estimated_seconds', '?')}s "
        f"(target {seconds}s) | "
        f"words: {internal.get('word_counts', {}).get('total', '?')} total",
        err=True,
    )
    if internal.get("repaired"):
        typer.echo("   (repair pass triggered — one section was regenerated)", err=True)


if __name__ == "__main__":
    app()
