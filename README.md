# RouteZero — Hybrid Token-Efficient Routing Agent

### AMD Developer Hackathon: ACT II · Track 1

> **Zero-token routing through fine-tuned DistilBERT on AMD MI300X, backed by a Qwen 14B local model and category-specialized Fireworks escalation.**

---

## 🏗️ Architecture Overview

```
                         ┌─────────────────────────┐
                         │   Incoming Task Prompt   │
                         └────────────┬────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │  Semantic Cache Lookup   │──── HIT ──→ Return (0 tokens)
                         │   (DistilBERT [CLS])     │
                         └────────────┬────────────┘
                                  MISS │
                                      ▼
                    ┌──────────────────────────────────┐
                    │     DistilBERT Router (66M)      │
                    │  Fine-tuned on AMD MI300X GPU    │
                    │     Zero-token classification     │
                    └───────┬──────────┬───────────────┘
                            │          │          │
                     easy (<30%)  uncertain   hard (≥65%)
                            │     (30-65%)        │
                            ▼          ▼          ▼
                    ┌──────────┐ ┌──────────┐ ┌──────────────────┐
                    │  Local   │ │  Local   │ │  Remote Models   │
                    │ Qwen 14B │ │ Qwen 14B │ │  via Fireworks   │
                    │          │ │ + forced │ │                  │
                    │ Few-shot │ │ agreement│ │ • Gemma 4 26B    │
                    │ examples │ │ verify   │ │ • Kimi K2        │
                    │ (free)   │ │          │ │ • Minimax M3     │
                    └────┬─────┘ └────┬─────┘ └────────┬─────────┘
                         │            │                 │
                         ▼            ▼                 ▼
                    ┌──────────────────────────────────────────┐
                    │     Deterministic Verifiers              │
                    │  Math · Logic · Sentiment · NER · Code   │
                    └──────────────────────────────────────────┘
```

---

## 🔥 AMD GPU Integration

### Training on AMD MI300X (ROCm)

The core innovation of this agent is a **fine-tuned DistilBERT binary classifier** that routes each query to the cheapest model that can answer it correctly — for **zero tokens**. This classifier was trained on **AMD Instinct MI300X** GPUs via the AMD Developer Cloud.

**Why AMD GPU matters here:**
- The MI300X's 192GB HBM3e memory and massive compute allowed rapid experimentation with training hyperparameters
- Training completed in **under 60 seconds** on MI300X vs. 5+ minutes on CPU
- ROCm + PyTorch integration was seamless: `torch.cuda.is_available()` works identically for AMD GPUs

**Training command (AMD Developer Cloud):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/rocm6.0
pip install transformers
python3 train_router_amd.py
```

### Training Results
```
Dataset:  173 examples (108 easy / 65 hard, 37.6% hard ratio)
Device:   AMD Instinct MI300X (ROCm)
Model:    distilbert-base-uncased → 2-class classifier
Epochs:   6
Accuracy: 81.8%
Recall:   100% (never misses a hard prompt)
```

---

## 🧠 Key Innovations

### 1. Three-Tier Confidence Routing
Instead of binary easy/hard, the router uses **softmax confidence scores** from DistilBERT:
- **Easy** (hard_prob < 0.30) → Local Qwen 14B with few-shot examples
- **Uncertain** (0.30–0.65) → Local Qwen 14B with **forced agreement verification** (two independent samples must agree)
- **Hard** (≥ 0.65) → Direct escalation to specialized remote models

### 2. Zero-Token Decision Making
The DistilBERT router makes routing decisions through a **local forward pass** — no API calls, no tokens consumed. The entire decision is invisible to the leaderboard's token counter.

### 3. Augmented Training Pipeline
The original tutorial dataset had only 3 hard examples out of 83 (3.6%). We augmented it to **173 examples with 37.6% hard ratio**, covering:
- Multi-step math with tricky edge cases
- Subtle Python bugs (closures, generators, race conditions)
- Ambiguous NER (e.g., "Paris Hilton" vs "Paris, France")
- Sarcasm detection in sentiment analysis
- Strict format constraints in summarization

### 4. Prompt Compression
Remote prompts are automatically compressed — filler words stripped, whitespace collapsed, code blocks preserved — saving **20-30 tokens per remote call**.

### 5. Free Few-Shot Examples
Local model prompts include category-specific few-shot examples at **zero leaderboard cost** (local tokens aren't scored), teaching the model the exact output format our verifiers expect.

### 6. Semantic Similarity Cache
DistilBERT's `[CLS]` embeddings power a cosine-similarity cache. Near-duplicate prompts (≥95% similarity) return cached answers instantly for **zero tokens**.

### 7. Category-Specialized Remote Models
When escalation is needed, prompts are routed to the **optimal model per category**:

| Category | Remote Model | Rationale |
|----------|-------------|-----------|
| Sentiment, NER, Factual, Summary | Gemma 4 26B | Best for language tasks + sub-prize eligibility |
| Math, Logic, Debug | Kimi K2 | Strongest reasoning without being a "thinking" model |
| Code Generation | Minimax M3 | Optimized for code synthesis |

---

## 📁 Repository Layout

```
agent/
  main.py              Entrypoint: env wiring, adaptive gates, atomic writeout
  router.py            Three-tier cascade: classify → cache → local → verify → escalate
  infer_router.py      DistilBERT inference (zero-token routing decisions)
  cache.py             Semantic similarity cache using [CLS] embeddings
  compress.py          Prompt compression for remote token savings
  prompts.py           Separate builders: terse (remote) vs enriched (local + few-shot)
  classifier.py        Deterministic zero-token category classifier
  verifiers.py         Format checks + math/logic agreement gate
  local_model.py       llama.cpp wrapper with warmup throughput probe
  fireworks_client.py  OpenAI client via FIREWORKS_BASE_URL, token accounting
  model_select.py      Rank ALLOWED_MODELS, ban reasoning models, Gemma routing
  config.py            All tunables (env vars)
  deadline.py          Global deadline manager

train_router_amd.py    DistilBERT training script (AMD ROCm / CUDA / CPU)
labeled_dataset.json   173-example augmented training dataset

Dockerfile             Portable multi-stage linux/amd64 build
.github/workflows/     CI/CD: auto-train router + build + push container
```

---

## 🚀 Quick Start

### 1. Train the Router (AMD GPU)
```bash
pip install torch --index-url https://download.pytorch.org/whl/rocm6.0
pip install transformers
python3 train_router_amd.py
```

### 2. Build the Container
```bash
docker buildx build --platform linux/amd64 -t token-router:local --load .
```

### 3. Run Locally
```bash
docker run --rm --env-file .env \
  -v "$PWD/tests/sample_input:/input:ro" \
  -v "$PWD/output:/output" \
  token-router:local
```

---

## 🎯 Submission

**Container:** `ghcr.io/abrarahnafkarim/token-router:latest`

**Platform:** `linux/amd64`

**Size:** < 10 GB compressed

---

## ⚙️ Tuning Knobs

| Variable | Default | Effect |
|----------|---------|--------|
| `FORCE_REMOTE` | 0 | 1 = Pure Fireworks mode (no local model) |
| `REMOTE_CATS` | "" | Comma-separated categories forced remote |
| `MIN_TPS` | 1.5 | Below this local tok/s → local disabled |
| `WEAK_TPS` | 4 | Below this → hard categories forced remote |
| `TIME_LIMIT` | 575 | Processing budget in seconds |
| `REMOTE_WORKERS` | 6 | Remote escalation concurrency |

---

*Built for the AMD Developer Hackathon: ACT II · Track 1: Hybrid Token-Efficient Routing Agent*
