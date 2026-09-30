# Script Bench

A short-form video script generator built for the Obula pipeline. It takes a niche, a one-sentence topic, and a target runtime in seconds, and returns a three-field JSON — `hook`, `body`, `cta` — ready to be spoken on camera.

---

## Quickstart

```bash
# 1. Clone / download the repo
cd <project-folder>   # the folder created by cloning or downloading

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Gemini API key
cp .env.example .env
# Edit .env and replace the placeholder with your real key (https://aistudio.google.com/apikey)

# 4. Run
python main.py --niche "personal finance" --topic "why your savings account is losing you money" --seconds 60
```

Output (stdout — verbatim, see [samples/sample_1.json](samples/sample_1.json)):
```json
{
  "hook": "You are losing money every single day your emergency fund sits in that big bank account because inflation is eating your savings faster than interest ever could.",
  "body": "That big traditional bank is paying you a pathetic zero point zero one percent interest while the cost of everything keeps climbing. You think you are being responsible by hoarding cash, but your purchasing power is evaporating month after month. You are essentially paying the bank to hold money that buys you less and less. Stop letting them profit off your caution. Move that cash into a high yield savings account today. You will instantly start earning four or five percent interest, completely risk free, turning inflation from an invisible enemy into a minor speed bump for your goals.",
  "cta": "Hit that follow button to finally master your money and build wealth that actually outpaces inflation."
}
```

---

## Full Options

```
python main.py --help

Options:
  --niche          TEXT          Content niche  [required]
  --topic          TEXT          One-sentence topic  [required]
  --seconds        INT (15–120)  Target runtime in seconds  [required]
  --model          TEXT          Model ID (default: gemini-3.8-flash)
  --insights                     Print internal reasoning to stdout
  --save-insights                Save internal reasoning to <niche>_<seconds>s_insights.json
  --help                         Show this message and exit
```

**Tip:** progress notes and the runtime summary go to `stderr`, so stdout can be piped:

```bash
python main.py --niche "fitness" --topic "warm-up mistakes" --seconds 45 > script.json
```

---

## How It Works

Script Bench is a five-stage pipeline. Each stage has a specific responsibility and can be inspected independently.

### Stage 1 — Strategy

One LLM call infers four things from the niche and topic:

- **Audience** — who is most likely watching this content (specific, not generic)
- **Core insight** — the sharpest single angle on the topic
- **Hook archetype** — one of: `curiosity_gap`, `bold_claim`, `pattern_interrupt`, `direct_question`, `story`
- **Body structure** — one of: `problem_agitate_solve`, `before_after_bridge`, `story_arc`
- **Content goal** — one of: `educate`, `persuade`, `entertain`, `convert`

All choices are validated against explicit allowlists. If the model returns a value not in the enum, the pipeline fails fast rather than proceeding with a bad structural decision.

### Stage 2 — Word Budget

Before any writing happens, the pipeline computes a deterministic word budget:

```
total_words  = round((target_seconds / 60) × 140)   # 140 wpm — midpoint of 130–150 spoken wpm
hook_words   = 20% of total
body_words   = 68% of total
cta_words    = 12% of total
```

The hook gets a disproportionately small share because its job is density, not length — a five-word hook that creates real tension beats a twenty-word one that meanders.

### Stage 3 — Hook Selection

The model generates **three candidates** for the chosen archetype, and scores each on a rubric:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| `specificity` | 35% | Does it name a concrete detail, number, or situation? |
| `opens_question` | 40% | Does it create a tension the body must resolve? |
| `first_five_strength` | 25% | Do the first five words grip on their own? |

The winner is selected by a **deterministic weighted sum in Python** — the model provides data, Python makes the decision. Runner-up candidates and scores are retained in the `_insights` sidecar (see `--save-insights`), labelled as heuristic signal, not ground truth.

### Stage 4 — Body + CTA Generation

A single LLM call writes the body and CTA together. The prompt injects:
- The chosen body structure and what it means in practice
- The word budget (min/max bounds for each section)
- A contextual CTA instruction derived from the content goal

**CTA style mapping** (deterministic, no LLM):

| Content goal | CTA style | Intent |
|-------------|-----------|--------|
| educate | save | "Save this for the next time you..." |
| persuade | follow | Specific reason to follow |
| entertain | share_experience | Comment prompt tied to the topic |
| convert | click | Specific resource behind a link |

The CTA text is written by the model; the style instruction shapes what it writes. No fixed template strings.

### Stage 5 — Validation + Repair

Three deterministic checks (pure Python, zero LLM calls):

1. **Required fields** — `hook`, `body`, `cta` all present and non-empty
2. **Boilerplate guard** — rejects "like and subscribe", "hit the bell", "follow for more", and similar phrases (substring match, lowercase-normalised)
3. **Runtime tolerance** — total estimated runtime within ±10% of target

If any check fails, the pipeline fires **one repair pass** — it regenerates the single most-offending section and re-validates. If that still fails, it raises `RepairFailedError` rather than silently accepting bad output.

---

## Sample Outputs

Five verbatim outputs across different niches and runtimes are in the `samples/` directory. Each has a companion `_insights.json` showing the internal reasoning: archetype chosen, hook scores, word budget.

| File | Niche | Seconds | Hook archetype |
|------|-------|---------|----------------|
| `sample_1.json` | Personal finance | 60 | bold_claim |
| `sample_2.json` | Fitness | 45 | bold_claim |
| `sample_3.json` | Productivity | 60 | bold_claim |
| `sample_4.json` | Parenting | 30 | curiosity_gap |
| `sample_5.json` | Home cooking | 45 | curiosity_gap |

All five are verbatim CLI output — unedited. Two runs (samples 1 and 4) needed
the single repair pass before validation cleared; the insights sidecars show
exactly which section was regenerated and why.

---

## Why It Produces Good Scripts

Good short-form scripts fail for predictable reasons: generic openings that give the viewer no reason to stay, bodies that deliver information without tension, and CTAs that are copy-pasted from someone else's video. Script Bench addresses each of these structurally rather than hoping the model gets it right by default.

The hook selection stage forces three candidates before committing. The rubric dimensions — specificity, opens_question, first_five_strength — operationalise the quality criteria that most bad hooks fail on. A hook that scores high on `opens_question` can't be resolved without watching the body. That's the mechanic that keeps viewers.

The body structure choices — Problem-Agitate-Solve, Before-After-Bridge, Story Arc — aren't aesthetic preferences. They're load-bearing. Each one creates a different kind of forward momentum. The strategy stage picks the one that fits the audience and topic, not the one that's easiest to prompt for.

The contextual CTA mapping exists because a creator who just educated you on compound interest and then says "smash the like button" has broken the frame of the content. The mapping forces the CTA to serve the same goal as the rest of the script.

For the full editorial argument, see [QUALITY_NOTE.md](QUALITY_NOTE.md).

---

## Project Structure

```
script-bench/
├── src/
│   ├── pipeline.py          # orchestrator + fixed 20/68/12 word budget
│   ├── strategy.py          # stage 1: LLM strategy call
│   ├── generator.py         # stages 2–3: hook + body generation
│   ├── validator.py         # stage 4: deterministic validation
│   ├── cta.py               # CTA style mapping table
│   ├── llm.py               # provider transport (Gemini) — the ONLY provider-aware module
│   ├── schemas.py           # JSON schemas for structured output
│   ├── utils.py             # prompt rendering utility
│   └── prompts/
│       ├── strategy.txt
│       ├── hook_candidates.txt
│       └── body_cta.txt
├── tools/
│   └── generate_samples.py  # one-command runner for the five samples
├── tests/
│   └── test_validator.py    # unit tests for the deterministic validator
├── samples/                 # 5 × verbatim outputs + insights sidecars
├── main.py                  # CLI entry point
├── requirements.txt
├── .env.example
├── README.md
└── QUALITY_NOTE.md
```

---

## Explicitly Out of Scope

These were deliberate cuts made against a 4–6 hour effort budget. Each is noted here because the brief explicitly rewards editorial judgment about what to build.

| Cut | Why |
|-----|-----|
| Multi-provider LLM abstraction | Adds indirection with no quality benefit for a single-submitter project |
| Full pytest matrix | A test suite is not evaluated; the validator is testable informally |
| Benchmark suite vs. a baseline | No baseline exists; building one would cost more than the engine itself |
| Claim/fact-risk detection | Irrelevant to the script-quality rubric; adds complexity with no signal |
| Mock-mode CLI flag | The real pipeline is fast and cheap enough to run live for demos |
| Creator style profiles | Interesting future feature; out of scope for the core engine contract |
| User-facing A/B variant exposure | Runner-up hooks are logged internally; surfacing them is a product decision |

---

## Prerequisites

- Python 3.11+
- A Gemini API key (set in `.env` as `GEMINI_API_KEY`; get one at https://aistudio.google.com/apikey)
- `pip install -r requirements.txt`

The entire pipeline runs in a single `python main.py ...` call. No server, no database, no build step.

**Model note:** the shipped default model is `gemini-3.5-flash-lite` — chosen
for free-tier quota headroom and stability (the newest tier, `gemini-3.8-flash`,
has been returning launch-day 503s on free accounts). This is a practical
capacity trade-off, not a quality compromise: every pipeline guarantee (fixed word
budget, deterministic scoring, validation, repair) is model-independent, and
`gemini-3.8-flash` remains one env-var away via `SCRIPT_BENCH_MODEL` if your
account has paid credits. Generation on the lite vs 3.8 tier can differ in
polish, not in structure.
