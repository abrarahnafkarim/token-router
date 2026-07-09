#!/usr/bin/env bash
# End-to-end test of the built image against a mounted input dir.
# Usage: scripts/run_local.sh [input_dir]   (default: tests/sample_input)
# FIX baked in: uses --env-file .env — plain $VARS would be silently empty.
set -euo pipefail
cd "$(dirname "$0")/.."
IN="${1:-tests/sample_input}"
if [ ! -f .env ]; then
  echo "no .env found; creating a placeholder from .env.example (edit it for real remote calls)"
  cp .env.example .env 2>/dev/null || echo "FIREWORKS_API_KEY=
FIREWORKS_BASE_URL=
ALLOWED_MODELS=" > .env
fi
[ -f .env ] || { echo "missing .env (see README Stage 3)"; exit 1; }
[ -f "$IN/tasks.json" ] || { echo "missing $IN/tasks.json"; exit 1; }
mkdir -p output
docker run --rm --env-file .env -e DEBUG=1 \
  -v "$PWD/$IN:/input:ro" -v "$PWD/output:/output" \
  token-router:local
echo; echo "== results.json =="
python3 -m json.tool output/results.json | head -60
[ -f output/stats.json ] && { echo; echo "== stats =="; python3 -m json.tool output/stats.json | head -30; }
