#!/usr/bin/env python3
"""
tools/generate_samples.py — One-command runner for the five submission samples.

Runs the full Script Bench pipeline across five topics with varied niches and
runtimes, writing each verbatim stdout JSON to samples/sample_N.json and the
--save-insights sidecar to samples/sample_N_insights.json.

Usage:
    python tools/generate_samples.py            # all five
    python tools/generate_samples.py --only 2   # just sample 2
    python tools/generate_samples.py --dry-run  # show what would run, exit

Failure policy: the batch STOPS after the 2nd failed run (repair-pass failure
or hard error) and reports — it never silently runs through all five.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"

# Stop the batch after this many failed runs (repair failure or hard error).
MAX_FAILURES = 2

# niche, topic, seconds — mirrors the README sample table
RUNS: list[dict] = [
    {
        "id": 1,
        "niche": "personal finance",
        "topic": "why your savings account is losing you money",
        "seconds": 60,
    },
    {
        "id": 2,
        "niche": "fitness",
        "topic": "warm-up mistakes that are killing your progress",
        "seconds": 45,
    },
    {
        "id": 3,
        "niche": "productivity",
        "topic": "why your to-do list makes you less productive",
        "seconds": 60,
    },
    {
        "id": 4,
        "niche": "parenting",
        "topic": "the two-minute rule that stopped bedtime tantrums",
        "seconds": 30,
    },
    {
        "id": 5,
        "niche": "home cooking",
        "topic": "the restaurant pasta secret hiding in your pantry",
        "seconds": 45,
    },
]


def build_cmd(run: dict) -> list[str]:
    return [
        sys.executable,
        "main.py",
        "--niche",
        run["niche"],
        "--topic",
        run["topic"],
        "--seconds",
        str(run["seconds"]),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the five submission samples.")
    parser.add_argument("--only", type=int, choices=[r["id"] for r in RUNS],
                        help="Run a single sample by id (1-5).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the commands without running them.")
    args = parser.parse_args()

    SAMPLES.mkdir(exist_ok=True)
    runs = [r for r in RUNS if args.only is None or r["id"] == args.only]

    if args.dry_run:
        for r in runs:
            print(f"sample_{r['id']}: {' '.join(build_cmd(r))}")
        return

    failures: list[int] = []
    completed: list[int] = []
    for r in runs:
        out_path = SAMPLES / f"sample_{r['id']}.json"
        ins_path = SAMPLES / f"sample_{r['id']}_insights.json"
        cmd = build_cmd(r)
        print(f"[{r['id']}/5] {r['niche']} | {r['seconds']}s -> {out_path.name}", flush=True)

        with out_path.open("w", encoding="utf-8") as out, ins_path.open("w", encoding="utf-8") as ins:
            proc = subprocess.run([*cmd, "--save-insights"], stdout=out, stderr=ins, cwd=ROOT)

        failed = proc.returncode != 0
        if failed:
            failures.append(r["id"])
            if proc.returncode == 1 and out_path.stat().st_size > 0:
                # Exit 1 = repair pass failed: stdout still holds the best-effort
                # public output — the pipeline's real result. Keep the file; the
                # failure report (which checks failed) is in the insights path.
                print(
                    f"    REPAIR-PASS FAILED (exit 1) — best-effort output kept in {out_path.name}, failure report in {ins_path.name}",
                    file=sys.stderr,
                )
            else:
                # Exit 2/3 = hard failure (parse/strategy/provider): no usable output.
                print(f"    FAILED (exit {proc.returncode}) — see {ins_path.name}", file=sys.stderr)
                out_path.unlink(missing_ok=True)

            if len(failures) >= MAX_FAILURES:
                skipped = [x["id"] for x in runs if x["id"] not in completed + failures]
                print(
                    f"\nStopping batch: {len(failures)} failed runs (samples {failures}). "
                    f"Samples not attempted: {skipped}",
                    file=sys.stderr,
                )
                break
            continue

        completed.append(r["id"])

        # Insights sidecar is written by the CLI to the project root; move it
        # into samples/ next to its sample (success path only).
        insights_file = ROOT / f"{r['niche'].lower().replace(' ', '_')[:20]}_{r['seconds']}s_insights.json"
        if insights_file.exists():
            insights_file.replace(ins_path)

    if failures:
        print(f"\n{len(failures)} run(s) failed: {failures}", file=sys.stderr)
        sys.exit(1)
    print("\nAll requested samples generated.")


if __name__ == "__main__":
    main()
