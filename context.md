# Script Bench — Project Context

Internal working notes for the Script Bench generator (Obula / Zypit internship
assignment). Not part of the submission package.

## Conventions

| Area | Decision | Notes |
|---|---|---|
| Language | Python 3.11+ | stdlib + typer + python-dotenv + google-genai |
| CLI | `typer`, single `generate` command | stdout = clean JSON `{hook, body, cta}`; all progress to stderr |
| Pipeline stages | Strategy → Runtime Budget → 3 Hook Candidates → Deterministic Hook Scoring → Body/CTA Generation → Deterministic Validation → ONE targeted repair | order fixed; one repair pass max, then `RepairFailedError` |
| Word budget | FIXED 20% hook / 68% body / 12% cta of `round(seconds/60 × 140)` | constants in `src/pipeline.py`; must stay fixed before sample generation |
| LLM provider | Google Gemini via `google-genai` SDK | `src/llm.py` is the ONLY provider-aware module |
| JSON output | Gemini native JSON mode (`response_mime_type` + `response_json_schema`) | schemas in `src/schemas.py`; shape constraint only — allowlists (strategy) and deterministic validation (validator) unchanged |
| Model | `gemini-3.8-flash` | chosen from the live models-list (2026-09-30): latest stable Flash generation, 1M in / 64K out, low latency, cheapest tier that reliably follows structured-output instructions for short JSON |
| Env var | `GEMINI_API_KEY` | never committed; `.env` is gitignored; optional `SCRIPT_BENCH_MODEL` overrides the model default |
| Samples | `samples/sample_N.json` + `sample_N_insights.json` | must be real pipeline output, unedited; `tools/generate_samples.py` runs all five; no quality-based re-rolls |
| Tests | `tests/test_validator.py` | validator only, pure Python, no LLM, runs in <1s |

## Decisions log

- **2026-09-25** — Built the 5-stage pipeline (commit `43fc42a`).
- **2026-09-30** — Fixed word budget to 20/68/12 (was 20/67/13); added validator
  unit tests; documented the self-assessed rubric limitation in QUALITY_NOTE.md.
- **2026-09-30** — Migrated transport from OpenAI SDK to `google-genai`
  (scoped exception to the architecture freeze; the funded key is a Gemini
  key). Pipeline stage order, prompts, scoring, validation, and sample
  strategy untouched. `src/llm.py` added so the rest of the codebase stays
  provider-independent — a provider swap touches one file plus env vars.
  Explicitly did NOT add a multi-provider abstraction (out of scope).
- **2026-09-30** — Active model switched to `gemini-3.5-flash-lite` for
  free-tier quota headroom on launch day of the brand-new `gemini-3.8-flash`
  (new-model free-tier caps are typically tighter/more volatile; the batch
  needs ~15–20 calls). Same call shape, same schemas — a transport-level
  choice, not a quality compromise.

## Open Questions

- **Model choice**: settled — `gemini-3.8-flash`, picked from the live
  models list for low latency and reliable short-JSON structured output.
  Revisit only if sample quality shows structured-output regression;
  `gemini-3.5-flash-lite` is the documented fallback candidate for cheaper
  lower-latency runs.
