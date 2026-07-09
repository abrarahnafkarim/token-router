# FIX_ACCURACY.md — Antigravity runbook to pass the accuracy gate

**Situation:** the submission ran successfully but scored below the minimum accuracy
threshold, so it is excluded from the leaderboard. The container is fine (valid JSON,
exit 0, no compliance problem). The answers were simply not correct enough.

**Root cause (most likely):** with default settings the agent answers most tasks with the
*local* model, and the local verifiers check answer *format*, not *truth*. So well-formed
but wrong local answers were kept for free and failed the judge. On a slow scoring machine,
some tasks may also have run out of time and been written empty, which the judge counts as
wrong.

**Strategy:** accuracy first, tokens second. You cannot rank until you clear the gate, so we
first make the agent answer everything with the strong remote model (high tokens, but it
*passes*), confirm it's on the leaderboard, then move categories back to local one at a time,
keeping only the ones that stay correct. This lowers tokens without dropping below the gate.

> **Rules for this runbook:** execute stages in order. Stop at each **CHECKPOINT** and show
> the user the output before continuing. Do not edit files under `agent/` except where Stage
> D explicitly says so. Ask before every `docker push` and before re-saving the submission.

---

## Stage A — Diagnose (no code changes yet)

You now have the real launch-day `ALLOWED_MODELS` and real Fireworks credentials. Put them in
`.env`, then find out where accuracy is actually being lost.

```bash
# 1. Confirm .env has the REAL launch-day values (edit if not):
grep -E "FIREWORKS_API_KEY|FIREWORKS_BASE_URL|ALLOWED_MODELS" .env

# 2. Print which models the agent selects as strong / language (sanity check the parser).
#    If "strong" is not actually the biggest/most-capable allowed model, that is itself a bug
#    to report to the user before continuing.
set -a; . ./.env; set +a
python3 -c "
from agent.model_select import choose, parse_allowed, size_of
import os
sel = choose(parse_allowed(os.environ.get('ALLOWED_MODELS','')))
print('strong  :', sel.get('strong'))
print('language:', sel.get('language'))
print('gemma?  :', sel.get('gemma'))
print('ranked  :', [(m.split('/')[-1], size_of(m)) for m in sel.get('all',[])])
"

# 3. Build the graded dev set and run the agent on it against REAL Fireworks,
#    with the LOCAL model active (this reproduces what happened at scoring).
python3 tests/make_devset.py
mkdir -p output
docker run --rm --env-file .env -e DEBUG=1 \
  -v "$PWD/tests/generated:/input:ro" -v "$PWD/output:/output" token-router:local

# 4. Grade it and read the per-category accuracy + token breakdown.
python3 tests/make_devset.py --judge output/results.json
python3 -c "import json;s=json.load(open('output/stats.json'));print('remote_calls',s['remote_calls'],'total_remote_tokens',s['total_remote_tokens'],'local_tps',s.get('local_tps'))"
```

**CHECKPOINT A.** Report to the user: the strong/language model picks, the per-category
accuracy table, and `local_tps`. The weak categories in that table are what sank the
submission. Common patterns:
- `local_tps` is low (e.g. < 4) → the box is slow; local answers are both weak and at risk of
  timing out. Force-remote will help most.
- factual / logic / summarization low, math / code okay → the local model is too weak on
  open-ended categories; those should go remote.

Do not proceed until the user has seen this.

---

## Stage B — Clear the gate now (pure Fireworks baseline)

This is the immediate fix. `FORCE_REMOTE=1` skips the local model entirely and answers every
task with the selected Fireworks models. Accuracy jumps to the model's own quality; tokens go
up, but the submission **passes and ranks** instead of being excluded.

```bash
# Verify accuracy in force-remote mode on the dev set first:
docker run --rm --env-file .env -e FORCE_REMOTE=1 -e DEBUG=1 \
  -v "$PWD/tests/generated:/input:ro" -v "$PWD/output:/output" token-router:local
python3 tests/make_devset.py --judge output/results.json
```

**CHECKPOINT B1.** If dev-set accuracy is now clearly high (most categories at or near 100%),
proceed to ship this baseline. If it is still low even in force-remote mode, the problem is not
the local model — STOP and report to the user (likely causes: wrong model selected as
`strong`, output-format mismatch with the judge, or empty answers from Fireworks errors —
check `stats.json` `remote_errors`).

Ship the baseline by baking `FORCE_REMOTE=1` into the image so the harness uses it:

```bash
# In the Dockerfile, change the FORCE_REMOTE default from 0 to 1.
```
Apply this exact edit to `Dockerfile` (the `ENV` block):
```
    FORCE_REMOTE=0 \
```
→
```
    FORCE_REMOTE=1 \
```
Then rebuild, push, and re-save the submission:
```bash
docker buildx build --platform linux/amd64 -t token-router:local --load .
python3 scripts/compliance_check.py
GHCR_USER=your_github_username GHCR_PAT=your_token bash scripts/push_image.sh
```

**CHECKPOINT B2.** Ask the user to re-save the submission on lablab and confirm it now passes
the accuracy gate and appears on the leaderboard. **Once it passes, you are safe** — everything
after this only lowers tokens, and you can always fall back to this baseline.

---

## Stage C — Real code hardening (raises accuracy, low risk)

One genuine latent weakness: when a task falls through to the last-resort path, it currently
prefers a short *local* generation and can even return an empty string. Empty answers are
scored wrong. Fix it so the backstop tries the strong *remote* model first, and never returns
empty while remote capacity remains.

In `agent/router.py`, replace the entire `_last_resort` method:

```python
    def _last_resort(self, cat, prompt):
        """Never leave an answer empty while any capacity remains."""
        if self.local and getattr(self.local, "ok", False):
            gen_toks = min(96, BASE_PLAN[cat]["lmax"])
            est = self.local.estimate(len(prompt) // 3, gen_toks)
            if self.dl.hard_remaining() > est + 2:
                try:
                    return self.local.gen(prompts.build(cat, prompt), gen_toks, 0.0)
                except Exception:
                    pass
        return ""
```

with:

```python
    def _last_resort(self, cat, prompt):
        """Never leave an answer empty. Prefer a remote answer for correctness,
        then a short local generation, then empty only if nothing is possible."""
        plan = BASE_PLAN[cat]
        if self.fw and self.fw.enabled and self.dl.hard_remaining() > 6:
            model = self._pick_model(plan)
            allowed = set(self.sel.get("all") or [])
            if model and (not allowed or model in allowed):
                try:
                    txt = self.fw.chat(model, prompts.build(cat, prompt),
                                       max_tokens=plan["rmax"])
                    if txt.strip():
                        _, fixed = V.verify(cat, txt, prompt)
                        return fixed if fixed.strip() else txt.strip()
                except Exception:
                    pass
        if self.local and getattr(self.local, "ok", False):
            gen_toks = min(96, plan["lmax"])
            est = self.local.estimate(len(prompt) // 3, gen_toks)
            if self.dl.hard_remaining() > est + 2:
                try:
                    return self.local.gen(prompts.build(cat, prompt), gen_toks, 0.0)
                except Exception:
                    pass
        return ""
```

Then verify nothing broke:
```bash
python3 tests/dry_run.py
python3 scripts/compliance_check.py
```

**CHECKPOINT C.** Both must pass (all dry-run checks green, no compliance failures). Report the
result.

---

## Stage D — Claw tokens back (only after the gate is passing)

Now reduce tokens by moving categories from remote to local, one group at a time, keeping only
the moves that hold accuracy. Do this by setting `REMOTE_CATS` (the list of categories to keep
remote) and turning `FORCE_REMOTE` back off.

The order below moves the *safest* categories local first — the ones whose local answers are
either deterministically checkable (code runs, JSON validates) or agreement-guarded
(math/logic), and leaves the open-ended ones (factual, summarization) remote longest.

```bash
# Attempt 1: everything remote EXCEPT the deterministically-verifiable categories.
docker run --rm --env-file .env \
  -e FORCE_REMOTE=0 \
  -e REMOTE_CATS="factual,summarization,sentiment,ner,logic" \
  -e DEBUG=1 \
  -v "$PWD/tests/generated:/input:ro" -v "$PWD/output:/output" token-router:local
python3 tests/make_devset.py --judge output/results.json
python3 -c "import json;s=json.load(open('output/stats.json'));print('total_remote_tokens',s['total_remote_tokens'])"
```

**CHECKPOINT D1.** Compare accuracy to the Stage B baseline. If it stayed above the gate (keep
a safety margin — do not sit right on the threshold), this config is better (fewer tokens, same
correctness). If accuracy dropped too far, that category group is too weak locally — revert to
the previous `REMOTE_CATS`.

Repeat, removing one category at a time from `REMOTE_CATS` (moving it local) and re-grading:

```bash
# Attempt 2: also move sentiment + ner local (they have structural verifiers).
-e REMOTE_CATS="factual,summarization,logic"
# Attempt 3: also move logic local (agreement-guarded).
-e REMOTE_CATS="factual,summarization"
# Attempt 4: also move summarization local.
-e REMOTE_CATS="factual"
# Attempt 5: everything local (only if factual holds accuracy locally).
-e REMOTE_CATS=""
```

Keep the **most-local config whose accuracy still clears the gate with margin.** That is your
lowest-token passing submission.

**CHECKPOINT D2.** Report the chosen `REMOTE_CATS` value, its dev-set accuracy, and its
`total_remote_tokens`, and confirm it beats the Stage B baseline on tokens while still passing.

Bake the winning config into the Dockerfile `ENV` block (set `FORCE_REMOTE=0` and the chosen
`REMOTE_CATS`, e.g.):
```
    FORCE_REMOTE=0 \
    REMOTE_CATS="factual" \
```
Rebuild, compliance-check, push, and re-save:
```bash
docker buildx build --platform linux/amd64 -t token-router:local --load .
python3 scripts/dry_run.py 2>/dev/null || python3 tests/dry_run.py
python3 scripts/compliance_check.py
GHCR_USER=your_github_username GHCR_PAT=your_token bash scripts/push_image.sh
```

**CHECKPOINT D3.** Ask the user to re-save the submission and confirm it still passes with a
better (lower) token count than the baseline.

---

## Guardrails

- **Never drop below the gate to chase tokens.** A passing high-token submission ranks; an
  excluded low-token one scores nothing. Keep an accuracy margin above the threshold.
- The dev-set judge in `tests/make_devset.py` is a *proxy*, not the real LLM judge — use it to
  compare configs, not to predict the exact gate. Leave margin.
- Every submission still must: read env at runtime, route all remote calls through
  `FIREWORKS_BASE_URL`, use only `ALLOWED_MODELS`, exit 0, stay under 10 minutes and 10 GB.
  Run `python3 scripts/compliance_check.py` before every push.
- If at any checkpoint accuracy is low even in full force-remote mode (Stage B), stop and
  surface it — that points to a model-selection or output-format problem, not the local model,
  and needs the user's input before further changes.
