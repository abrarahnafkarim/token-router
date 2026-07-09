# =============================================================================
# Hybrid Token-Efficient Routing Agent — AMD Dev Hackathon ACT II, Track 1
#
# Build (ALWAYS linux/amd64 — the harness rejects other architectures):
#   docker buildx build --platform linux/amd64 -t token-router:local --load .
#
# CRITICAL portability fix: GGML_NATIVE=OFF prevents -march=native, so the
# llama.cpp binary runs on the UNKNOWN scoring host (AVX2 baseline covers
# every x86-64 server CPU of the last decade, incl. all AMD EPYC). Without
# this, an image built on a newer CPU dies with "illegal instruction" on an
# older one — a silent, unrecoverable disqualifier.
# =============================================================================
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_AVX2=ON" \
    FORCE_CMAKE=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ---- runtime stage: no compilers, just libgomp (OpenMP) for llama.cpp ------
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY agent/ ./agent/
COPY models/ ./models/

# ---- tuning knobs (day-of changes happen HERE; the harness only injects ----
# ---- FIREWORKS_API_KEY, FIREWORKS_BASE_URL, ALLOWED_MODELS)             ----
ENV LOCAL_MODEL_PATH=/app/models/local.gguf \
    TIME_LIMIT=575 \
    TIME_RESERVE=30 \
    REMOTE_WORKERS=6 \
    SIMPLE_MODE=1 \
    SIMPLE_MAX_TOKENS=2048 \
    MIN_TPS=1.5 \
    WEAK_TPS=4 \
    LOCAL_CTX=8192
# Architecture B (pure Fireworks token-golf): uncomment to flip.
# ENV FORCE_REMOTE=1
# Force specific categories remote regardless of local speed, e.g.:
# ENV REMOTE_CATS=math,logic

ENTRYPOINT ["python", "-m", "agent.main"]
