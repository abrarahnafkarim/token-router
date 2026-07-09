# FIX_ACCURACY_V2.md — get from 26% to 80%+

**Why 26% happened:** a strong Fireworks model does not score 26% on these eight categories.
That number means correct answers were not reaching the judge intact — some tasks came back
**empty** (API errors or deadline timeouts, scored as wrong), and others were **corrupted by
our own pipeline**: verifiers that rewrite the answer, prompt additions that fight the task's
own instructions, and `max_tokens` caps that truncate math/code mid-answer. The efficiency
machinery is what sank accuracy.

**The fix:** run a dead-simple accuracy-first mode first — one clean call to the strongest
model, generous tokens, raw answer shipped, empties retried. Prove it clears 80%. Only then
add token efficiency back. A new `SIMPLE_MODE` is already built and tested for this.

> Execute in order. Stop at each **CHECKPOINT**. Ask before any `docker push` or re-saving the
> submission.

---

## FIX 1 — Ship accuracy-first mode (do this now)

`SIMPLE_MODE=1` bypasses the local model, classifier, verifiers, and all normalization. It
sends each task's prompt **untouched** to the strongest allowed model, ships the model's **raw**
reply, and retries any empty answer once. Nothing can truncate or reformat a correct answer.

```bash
# Confirm .env has the REAL launch-day values.
grep -E "FIREWORKS_API_KEY|FIREWORKS_BASE_URL|ALLOWED_MODELS" .env

# Grade accuracy-first mode on the dev set against real Fireworks.
set -a; . ./.env; set +a
python3 tests/make_devset.py
mkdir -p output
docker run --rm --env-file .env -e SIMPLE_MODE=1 -e DEBUG=1 \
  -v "$PWD/tests/generated:/input:ro" -v "$PWD/output:/output" token-router:local
python3 tests/make_devset.py --judge output/results.json
python3 -c "import json;r=json.load(open('output/results.json'));print('empty answers:',sum(1 for x in r if not x['answer']),'of',len(r))"
```

**CHECKPOINT 1.** Two numbers matter: **empty-answer count** (must be 0) and **accuracy**.
- If empties > 0 → FIX 2.
- If accuracy is high (≥80% on the proxy, with margin) → go to FIX 3 and ship.
- If empties are 0 but accuracy is still low → FIX 4.

---

## FIX 2 — Kill empty answers (if any appeared)

Empty answers are scored wrong, and each empty is pure lost accuracy. If FIX 1 showed empties,
the cause is API errors or slow completions running into the deadline.

```bash
# Read the error count and model that was used.
python3 -c "import json;s=json.load(open('output/stats.json'));print('remote_errors',s.get('remote_errors'),'calls',s.get('remote_calls'))" 2>/dev/null || true

# Prove a single clean call to the chosen model actually works:
set -a; . ./.env; set +a
python3 -c "
import os
from agent.model_select import choose, parse_allowed
from agent.fireworks_client import Fireworks
sel = choose(parse_allowed(os.environ['ALLOWED_MODELS']))
fw = Fireworks()
print('model:', sel.get('strong'))
print('reply:', fw.chat(sel['strong'], 'What is the capital of France?', max_tokens=64))
print('tokens:', fw.total_tokens, 'errors:', fw.errors)
"
```

If that single call **errors**: the model ID or base URL is the problem — the exact
`FIREWORKS_BASE_URL` / model string from the launch-day guide must be used verbatim. Report the
error text to the user.

If the single call **works** but the batch had empties: it's throughput vs. the deadline. Raise
concurrency and retries, then re-run FIX 1:
```bash
# add these to the docker run in FIX 1:
  -e SIMPLE_WORKERS=24 -e REMOTE_TIMEOUT=40
```

**CHECKPOINT 2.** Re-run FIX 1's grading. Proceed only when empty answers = 0.

---

## FIX 3 — Bake it in and submit

Once FIX 1 clears the gate on the dev set, make `SIMPLE_MODE` the image default.

Edit the `Dockerfile` `ENV` block — add `SIMPLE_MODE=1` (leave the others):
```
    FORCE_REMOTE=0 \
    SIMPLE_MODE=1 \
```
Then:
```bash
docker buildx build --platform linux/amd64 -t token-router:local --load .
python3 scripts/compliance_check.py
GHCR_USER=your_github_username GHCR_PAT=your_token bash scripts/push_image.sh
```

**CHECKPOINT 3.** Ask the user to re-save the submission and confirm the real harness now
reports ≥80%. **Getting on the board is the priority — do this before any token optimization.**

---

## FIX 4 — If accuracy is still low with zero empties

Then the answers arrive intact but are wrong. Likely causes, in order:

1. **Wrong model is being selected as `strong`.** Verify the pick is truly the most capable
   allowed model:
   ```bash
   set -a; . ./.env; set +a
   python3 -c "
   from agent.model_select import choose, parse_allowed, size_of
   import os
   sel=choose(parse_allowed(os.environ['ALLOWED_MODELS']))
   print('strong picked:', sel['strong'])
   print('all ranked   :', [(m.split('/')[-1], size_of(m)) for m in sel['all']])
   "
   ```
   If `strong` is not the biggest/most-capable model, force it explicitly for the next run:
   ```bash
   # pick the correct strongest ID from the list above, then:
   -e SIMPLE_FORCE_MODEL="accounts/fireworks/models/<the-strong-one>"
   ```
   (If this env is honored — see note below — it overrides selection.)

2. **`max_tokens` truncation on long answers** (math with steps, code). Raise it:
   ```bash
   -e SIMPLE_MAX_TOKENS=2048
   ```

3. **The proxy judge is stricter than the real one.** Our `tests/make_devset.py` judge is only
   a proxy. If the *real* harness scores higher than the proxy, trust the real harness. Confirm
   by shipping FIX 3 and reading the real score, not the proxy.

**CHECKPOINT 4.** Report which cause applied and the new accuracy. If none of these lift it and
the strongest model genuinely can't clear 80% on clean prompts, the bottleneck is model
capability, not our code — surface that to the user with the per-category proxy table so they
can decide.

> Note: `SIMPLE_FORCE_MODEL` is referenced above as an optional override. If it is not yet
> supported in `agent/simple.py`, add it: read `os.environ.get("SIMPLE_FORCE_MODEL")` at the top
> of `run_simple` and, if set and present in `allowed`, use it as `model`. Keep the change
> minimal and re-run `python3 tests/dry_run.py` afterward.

---

## FIX 5 — Only after you're passing: claw tokens back

`SIMPLE_MODE` is accuracy-first, not token-efficient — it uses the big model on every task with
large `max_tokens`. Once you are safely above 80% on the real harness, lower tokens **while
watching accuracy stay above the gate with margin**, in this order:

1. Lower `SIMPLE_MAX_TOKENS` step by step (1024 → 640 → 448 → 320), re-grading each time. Stop at
   the smallest value that still clears 80% with margin.
2. Then, if you want to reclaim the zero-cost local path, switch `SIMPLE_MODE=0` and use the
   routed pipeline with `REMOTE_CATS` (see FIX_ACCURACY.md Stage D) — but only move a category
   local if its accuracy holds. The routed pipeline's local answers were part of what failed
   before, so re-introduce them one at a time and keep only the ones that stay correct.

Never trade below the gate for tokens: a passing high-token submission ranks; an excluded
low-token one scores zero.
