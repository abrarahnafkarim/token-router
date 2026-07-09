# Hybrid Token-Efficient Routing Agent — AMD Developer Hackathon ACT II (Track 1)

An autonomous agent that reads `/input/tasks.json`, answers 8 task categories, and
writes `/output/results.json`. It answers as much as possible with a **local GGUF
model at zero scored-token cost**, verifies every answer deterministically, and
**escalates only verified failures** to a single minimal Fireworks call — routed
through **Gemma** where it can be, to stay eligible for the *Best Use of Gemma via
Fireworks* sub-prize.

> **Scoring recap.** Two gates: (1) an LLM-Judge accuracy threshold — below it you're
> excluded from the leaderboard; (2) among passers, rank by **ascending token count**
> recorded at the Fireworks proxy. Local tokens count as **zero**. So the game is:
> answer everything you can prove correct locally, spend the fewest possible remote
> tokens on the rest, and never fail the accuracy gate.

---

## How this design wins (and where it hedges)

- **Cascade, not a probabilistic router.** Off-the-shelf routers (RouteLLM,
  semantic-router) optimize *dollar cost* and route *without checking the answer*.
  Here the "cheap tier" is a local model at **zero** scored cost and the escalation
  trigger is **deterministic verification**, so we only spend remote tokens on tasks
  we can *prove* the local model got wrong.
- **The accuracy-gate guard.** Math and logic are escalated unless **two independent
  local samples agree** on the final answer — a wrong problem setup rarely reproduces
  itself under sampling noise, which a naive "recompute the arithmetic" check would
  miss and wave through into a gate failure.
- **Category-conditional escalation.** Hard escalations (math, logic, code) go to the
  strongest allowed non-reasoning model; language escalations (factual, NER, sentiment,
  summary) go to Gemma — sub-prize eligibility without betting the gate on Gemma.
- **Hedged against the unknown scoring box.** Hardware specs aren't published. A warmup
  probe measures local tokens/sec: too slow → hard categories go remote; far too slow or
  no GGUF → the agent silently becomes **pure-Fireworks (Architecture B)**. Set
  `FORCE_REMOTE=1` to force B.

---

## For the Google Antigravity agent

Open this folder as a Workspace, then instruct: *"Follow README.md stage by stage.
Run each bash block, stop after each stage, and show me the output before continuing."*
Standing rules are in `AGENTS.md`. Keep Antigravity in **Review-driven** mode and
approve `docker`, `git`, and `python3` when prompted. Never commit `.env` or `models/`.

---

## Stage 0 — Verify the environment
```bash
echo "== OS ==";        grep -E "PRETTY_NAME|VERSION_ID" /etc/os-release
echo "== Docker ==";    docker --version && docker info 2>/dev/null | grep -i "Server Version"
echo "== Buildx ==";    docker buildx version
echo "== Python ==";    python3 --version
echo "== Git ==";       git --version
echo "== Disk (need >12GB free) =="; df -h . | tail -1
echo "== Fireworks reachable =="; curl -sSI https://api.fireworks.ai | head -1
```
Expect: Ubuntu 24.04, Docker with buildx, Python ≥3.10, ≥12 GB free.

## Stage 1 — Sanity-check the code offline (no Docker, no GGUF, no creds)
```bash
python3 tests/dry_run.py            # 38 checks: classifier, verifiers, agreement, routing
python3 scripts/compliance_check.py # instant-DQ scan
```
Both must pass before you build. `dry_run.py` mocks the model and Fireworks, so it runs
anywhere in seconds.

## Stage 2 — Download the local model (~2.5 GB → `models/local.gguf`)
```bash
bash scripts/download_model.sh
ls -lh models/local.gguf
```
This is **Qwen3-4B-Instruct-2507, Q4_K_M** — a *non-thinking* model (emits no `<think>`
blocks: no stray tokens, fast CPU decode). `models/` is git-ignored; the weights are
baked into the image at build time, never committed to git.

## Stage 3 — Local dev credentials (never shipped)
```bash
cp .env.example .env
# edit .env: put your real dev FIREWORKS_API_KEY, and on launch day the real ALLOWED_MODELS
grep -q "^\.env$" .gitignore && echo ".env is git-ignored ✓"
```
> **Warning:** `.env` is for local testing only. The submitted image reads these three
> variables from the OS environment (injected by the harness). Never `COPY .env` into the
> image and never hardcode a key — `compliance_check.py` fails the build if you do.

## Stage 4 — (Optional) run the agent locally without Docker
Fast iteration on the router logic on your CPU box:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # compiles llama-cpp-python (needs build-essential, cmake)
set -a; . ./.env; set +a
LOCAL_MODEL_PATH="$PWD/models/local.gguf" DEBUG=1 \
INPUT_PATH=tests/sample_input/tasks.json OUTPUT_PATH=output/results.json \
python3 -m agent.main
python3 -m json.tool output/results.json
deactivate
```

## Stage 5 — Build the image (portable linux/amd64)
```bash
docker buildx create --use --name actii 2>/dev/null || docker buildx use actii
docker buildx build --platform linux/amd64 -t token-router:local --load .
docker images token-router:local
```
The Dockerfile compiles llama.cpp with `GGML_NATIVE=OFF` (AVX2 baseline) so it can't
crash with an illegal instruction on a scoring CPU older than your build machine.
Platform is set by the buildx flag — do not hardcode it in `FROM`.

## Stage 6 — End-to-end container test with a mock harness
```bash
bash scripts/run_local.sh
```
Runs the container against `tests/sample_input/`, prints `results.json`, and (with
`DEBUG=1`) a per-category routing + **total remote token** breakdown from
`output/stats.json`. This is your optimization dashboard: watch `TOTAL_REMOTE_TOKENS`
fall as you push more categories local.

Force the pure-Fireworks fallback to sanity-check Architecture B:
```bash
docker run --rm --env-file .env -e FORCE_REMOTE=1 -e DEBUG=1 \
  -v "$PWD/tests/sample_input:/input:ro" -v "$PWD/output:/output" token-router:local
```

## Stage 7 — Push to a public registry
```bash
GHCR_USER=your_github_username GHCR_PAT=ghp_your_write_packages_token \
  bash scripts/push_image.sh
```
Then on GitHub: **Profile → Packages → token-router → Package settings → Change
visibility → Public.** (Docker Hub alternative is in `scripts/push_image.sh` comments.)
Re-run `docker images` — the registry compresses ~2–3×, so the ~4 GB local image lands
well under the 10 GB compressed cap.

## Stage 8 — Submit on lablab.ai
Provide: title, short + long description, tags, **cover image**, **video**, **slide
deck**, **public GitHub repo (this README)**, demo URL, and the **public image reference**
`ghcr.io/YOU/token-router:latest`. Submit before the deadline (**July 11, 2026, 15:00
UTC** — confirm on the event page).

## Stage 9 — Launch-day checklist (models published that day)
```bash
# 1. Paste the REAL ALLOWED_MODELS into .env; confirm Gemma + a strong non-reasoning model.
# 2. python3 tests/dry_run.py && python3 scripts/compliance_check.py
# 3. bash scripts/run_local.sh        # check answers + TOTAL_REMOTE_TOKENS
# 4. Rebuild + push (Stages 5,7). Submit ONE probe early to read the leaderboard.
# 5. Tune, staying within 10 submissions/hour:
#      - too many escalations? raise local coverage (verifiers already gate quality)
#      - accuracy gate at risk? add categories to REMOTE_CATS (e.g. math,logic)
#      - scoring box slow/timing out? set FORCE_REMOTE=1 (Architecture B)
#      - organizers confirm remote-only? FORCE_REMOTE=1
```

---

## Day-of tuning knobs (Dockerfile `ENV`, or `-e` at run time)

| Var | Default | Effect |
|-----|---------|--------|
| `FORCE_REMOTE` | 0 | 1 = Architecture B (pure Fireworks, no local model) |
| `REMOTE_CATS` | "" | comma list always routed remote, e.g. `math,logic` |
| `MIN_TPS` | 1.5 | below this local tok/s → local disabled entirely |
| `WEAK_TPS` | 4 | below this → hard categories forced remote |
| `TIME_LIMIT` | 575 | processing budget (s); hard cap is 600 |
| `REMOTE_WORKERS` | 6 | remote escalation concurrency |
| `DEBUG` | 0 | 1 = write `output/stats.json` |

## Repository layout
```
agent/
  main.py            entrypoint: env wiring, adaptive gates, atomic writeout, exit 0
  config.py          all tunables (env vars)
  classifier.py      deterministic zero-token category classifier
  prompts.py         terse single-shot templates + dynamic max_tokens
  local_model.py     llama.cpp wrapper, warmup throughput probe, graceful degrade
  fireworks_client.py OpenAI client via FIREWORKS_BASE_URL, token accounting
  model_select.py    rank ALLOWED_MODELS, ban reasoning models, Gemma routing
  verifiers.py       zero-cost checks + math/logic agreement gate
  router.py          the cascade: classify→local→verify→escalate-once
deadline.py          global deadline manager
scripts/             download_model, run_local, push_image, compliance_check
tests/               dry_run (offline), mock_fireworks, sample_input
Dockerfile           portable multi-stage linux/amd64 build
```

## Compliance (each is an instant zero — `compliance_check.py` scans for them)
- Env vars read from the environment only; no `.env` in image; no hardcoded key.
- Every remote call via `FIREWORKS_BASE_URL`; every model asserted ∈ `ALLOWED_MODELS`;
  no reasoning/thinking models.
- No hardcoded or cached answers (evaluation uses unseen prompt variants).
- `linux/amd64`, ≤10 GB compressed, exits 0, ≤10 min.
- Public repo + README; original work; MIT-licensed.
