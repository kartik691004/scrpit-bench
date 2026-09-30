# What "Good" Means for a Short-Form Script — and How This Generator Pursues It

## The Problem With Most Generated Scripts

Ask a language model to "write a 60-second script about personal finance" and you'll get something serviceable: a topic sentence, three supporting points, a call to action. It reads well. It wouldn't keep anyone watching.

Short-form video scripts live or die on three things that prose doesn't require: **attention**, **retention**, and **action**. A good script earns each one structurally, not by being well-written in the literary sense.

---

## What "Good" Actually Means

**A good hook doesn't describe the video. It creates a reason to watch it.**

The difference between "Today I'm going to explain why savings accounts lose money" and "Your savings account is making you poorer. Here's the math they don't show you." is not style — it's tension. The first tells the viewer what they're about to receive. The second opens a gap that can only be closed by watching the rest.

Specificity matters here more than creativity. A hook that names a number, a situation, or a person is harder to scroll past than one that stays abstract. The first-five-words test exists because that's roughly how long a viewer takes to decide whether to continue.

**A good body doesn't just deliver information. It resolves the tension the hook created.**

The body structure isn't decoration. Problem-Agitate-Solve works for topics where the audience already feels the problem but hasn't named it sharply enough. Before-After-Bridge works when the transformation is the story — the mechanism is the insight. Story Arc works when the creator's credibility comes from experience, not expertise.

Choosing the wrong structure for the topic is how scripts become "interesting but forgettable." The body needs to feel inevitable given the hook — like it couldn't have been written any other way.

**A good CTA earns its place instead of interrupting the content.**

The CTA is the hardest part to get right because most default CTAs ("like and subscribe", "follow for more") break the frame of whatever just happened. A creator who just spent 55 seconds making you feel something, then asks you to "smash the like button," has ended the script three seconds early.

A contextual CTA extends the content's logic. If the script educated you, the CTA invites you to save it for the next time you need it. If it entertained you, it invites you to add to the story. If it converted, it tells you exactly what you get when you click. The specificity of the CTA signals whether the creator thought about you or about their metrics.

---

## How This Generator Pursues These Standards

**The hook selection stage operationalises the quality criteria.** Generating three candidates and scoring them on specificity, tension-creation, and opening strength forces the model to produce variation before committing. The rubric dimensions aren't arbitrary — they map directly to the failure modes of bad hooks. A hook that scores low on `opens_question` is one the viewer can resolve without watching on. That's a bad hook.

**One known limitation, stated plainly: the rubric scores are self-assessed.** The same model that generates the three hook candidates also assigns their specificity, opens_question, and first_five_strength scores. There is no independent judge. Python's weighted-sum selection is deterministic and honest about the data it receives — but nothing external verifies the scores themselves, and a model can be confidently wrong about its own writing. In practice this makes the rubric a structured self-criticism pass: it reliably forces variation between candidates and produces a defensible ordering, but the absolute scores should be read as heuristic signal, not ground truth. A stronger design would score candidates with a separate judge model or human review; that is deliberately out of scope for this build, and the runner-up scores retained in the `_insights` sidecar carry exactly that caveat.

**A second known limitation, stated as plainly: the strategy stage collapses body-structure diversity.** All five sample outputs — spanning personal finance, fitness, productivity, parenting, and home cooking — selected `problem_agitate_solve` as the body structure, despite the stage being designed to choose among three structures (`problem_agitate_solve`, `before_after_bridge`, `story_arc`). The hook archetype did vary (three `bold_claim`, two `curiosity_gap`); the structure choice did not vary at all. This is a limitation of the current strategy prompt, which under-constrains structure choice relative to archetype: the three structures are listed, but nothing in the prompt forces the model to argue why the chosen one beats the other two for this specific audience and topic, so the model defaults to the most familiar short-form pattern every time. The pipeline accepts the choice — it is on the allowlist — and no deterministic check exists for structure fit. A stronger design would require the strategy stage to justify the structure against the alternatives, or derive it deterministically from topic features.

**The structural choices are made before writing begins.** Separating the strategy stage from generation means the model writes the body knowing exactly what structure it's following and why. A model told to "write a compelling body" will default to its training distribution. A model told to "follow the problem-agitate-solve structure for an audience that feels guilty about their savings habits" has a specific job.

**The CTA style mapping prevents the easiest mistake.** Mapping content goal to CTA style deterministically means the CTA can't accidentally be "follow for more" on an educational script. The instruction shapes the model's output; the validator catches anything that slips through.

**The validator closes the feedback loop.** A script that estimates at 80 seconds when the target was 60 isn't a good 60-second script — it's a 60-second script that will get cut off. The runtime check ensures the output is actually usable, not just coherent.

---

## What This Generator Doesn't Do — and Why That's Honest

It doesn't verify claims. It doesn't profile creator voice. It doesn't run A/B tests on the hook candidates at scale. These would all make it better in a broader sense, but they're not what makes a script good in the 4–6 hours of effort this project targets.

The deliberate bet here is that structure is the biggest leverage point. Most generated scripts fail not because the writing is bad but because the framing is wrong — the hook doesn't create tension, the body doesn't resolve it, the CTA doesn't fit. Getting those three things right, consistently, is what this generator is built to do.
