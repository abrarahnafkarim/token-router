# Hybrid Token-Efficient Routing Agent — Project Brief (NotebookLM Source)

> This is the single source document for generating a hackathon video presentation.
> It is written to be read aloud and narrated. Facts marked **[ASSUMPTION]** or
> **[UNVERIFIED]** are open questions the design deliberately hedges against — narrate
> them as such, never as settled fact.

---

## 1. What this project is

This is an autonomous AI agent submitted to **Track 1 of the AMD Developer Hackathon:
ACT II**. The track is a *Hybrid Token-Efficient Routing Agent*: given a batch of
natural-language tasks spanning eight capability categories, the agent must answer them
correctly while spending as few remote API tokens as possible.

The agent runs as a Docker container. It reads a list of tasks from `/input/tasks.json`,
solves each one, and writes answers to `/output/results.json` before exiting. It has a
hard ten-minute runtime limit and the image must be under ten gigabytes compressed.

The eight categories are: factual knowledge, multi-step mathematical reasoning, sentiment
classification with justification, text summarization to a length constraint, named-entity
recognition, code debugging, logical and deductive reasoning, and code generation from a
specification.

---

## 2. The scoring, and why it is counterintuitive

Submissions are judged on two axes, in order.

First, an **accuracy gate**. An LLM-based judge evaluates every answer. If the submission's
accuracy falls below a threshold, it is *excluded from the leaderboard entirely*. There is
no partial credit for a fast-but-wrong agent — failing the gate means scoring nothing.

Second, among the submissions that pass the gate, ranking is by **total tokens recorded at
the Fireworks proxy, ascending**. Fewer tokens means a higher rank.

The counterintuitive part is this: **tokens spent on a local model, running inside the
container, count as zero.** Only remote calls through the Fireworks API are metered. So the
optimal strategy is not "use the biggest model" or "write the cleverest prompt." It is:
*answer as many tasks as you can locally for free, and spend remote tokens only on the few
you genuinely cannot.* Routing intelligence wins, not raw compute.

This reframes the whole problem. The agent is performing arbitrage between two budgets: a
**time budget** on the local side (a small model on unknown, possibly CPU-only hardware is
slow) and a **token budget** on the remote side (every API token costs leaderboard rank).

---

## 3. The core design: a cascade, not a router

Most published "LLM routers" — systems like RouteLLM or semantic-router — were built to
save money. They predict, before generating anything, whether a query needs a strong or a
weak model, and they route probabilistically. Crucially, they never check whether the
answer they got was actually correct.

That is the wrong tool here, for two reasons. It optimizes dollar cost, but our cheap tier
costs *zero*, not "less." And it routes blind, but our whole edge comes from *knowing* when
the local answer is good enough to keep.

So this agent uses a **verify-then-escalate cascade** instead. The flow for every task is:

1. **Classify** the task into one of the eight categories using a deterministic,
   zero-token classifier — plain pattern matching, no model call, because a model-based
   router would tax every single task with either tokens or time.
2. **Generate** an answer locally with a small model, at zero scored cost.
3. **Verify** that answer with a cheap, deterministic check.
4. **Escalate** to a single minimal Fireworks call *only if the verification fails.*

The result: remote tokens are spent exclusively on tasks the agent can *prove* the local
model got wrong. Everything it can validate locally is free.

---

## 4. The one mechanism worth remembering: agreement guards the gate

The most dangerous categories are math and logic. A small model will often produce a
confidently stated but wrong answer — and a naive verifier that just re-checks the
arithmetic would happily confirm it, because the model set the problem up wrong in the
first place. That false confidence is exactly what fails the accuracy gate, and failing the
gate is catastrophic.

The fix is an **agreement check**. For math and logic, the agent generates the answer
*twice* locally — once deterministically, once with sampling noise. If the two independent
samples reach the same final answer, it is trusted and kept for free. If they disagree, the
agent does not trust either one and escalates to a strong remote model.

The insight is that a genuinely-understood problem reproduces its own answer under noise,
while a lucky guess or a wrong setup usually does not. This trades a few remote tokens on
the shaky tasks to protect the accuracy gate — the right trade, because tokens cost rank
but a gate failure costs everything.

---

## 5. The engineering that makes it robust

**Category-conditional escalation for a second prize.** There is a separate one-thousand
dollar sub-prize for *Best Use of Gemma via Fireworks*. When the agent does escalate, it
routes language tasks — factual, sentiment, NER, summarization — to a Gemma model, keeping
that prize in play. Harder escalations — math, logic, code — go to the strongest available
non-reasoning model, because on those the accuracy gate matters more than prize eligibility.

**A hard rule against reasoning models.** So-called reasoning or thinking models emit long
internal chains of thought, and those thinking tokens are billed as output. On a track
scored by token count, they are poison. The agent parses the allowed-model list at runtime
and refuses to select any model whose name marks it as a reasoning variant.

**Adaptive degradation.** The agent measures the local model's actual throughput at startup.
If the hardware is slow, it moves the hard categories to remote. If the local model is
missing or far too slow, it silently becomes a pure-Fireworks agent — a second architecture,
built in, flipped by a single switch. It never crashes; it degrades.

**A portable build.** The container compiles its local inference engine with a
conservative, portable instruction set, so it cannot crash with an illegal-instruction
error on a scoring machine whose processor differs from the build machine. Whatever happens,
the agent always writes a valid results file and exits cleanly, so the run is always
scoreable.

---

## 6. Honesty: the open questions the design hedges against

A credible submission names its own risks. Three facts are genuinely unknown at build time,
and the architecture is shaped around not knowing them.

- **[UNVERIFIED] The scoring hardware.** The organizers say submissions run on a
  standardized environment but do not publish its specifications — it may be CPU-only, it
  may have a GPU. The agent's throughput probe and degradation logic exist precisely because
  this is unknown.
- **[UNVERIFIED] Whether local inference is fully permitted.** The public track description
  clearly rewards a hybrid local-plus-remote design where local tokens count as zero. One
  line in the participant guide is worded ambiguously about routing all inference through
  Fireworks. The coherent reading is that all *remote* inference must go through the proxy so
  it can be metered — but this is confirmed on the event's channel on launch day, and the
  pure-remote fallback exists in case the answer is restrictive.
- **[ASSUMPTION] The exact model list.** The permitted models are published only on launch
  day. The agent therefore never hardcodes a model; it parses the list at runtime, ranks the
  models by size, and picks appropriately. No accuracy or token numbers are claimed in
  advance, because the real figures depend on models not yet revealed and on tasks not yet
  seen.

These are not oversights. They are the reason the design is adaptive rather than tuned to a
single guessed configuration.

---

## 7. The one-sentence summary

This agent wins by treating the leaderboard for what it actually measures — remote tokens
avoided without failing the accuracy gate — and answers everything it can prove correct on a
free local model, escalating only verified failures, guarding the gate with an agreement
check on the tasks most likely to fool it, all while staying robust to a scoring
environment it cannot see in advance.
