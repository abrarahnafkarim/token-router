#!/usr/bin/env bash
# Downloads the local GGUF (Qwen3-4B-Instruct-2507, Q4_K_M, ~2.5 GB) to
# models/local.gguf. This model is NON-THINKING (no <think> blocks): no
# stray tokens, fast CPU decode. Run on the HOST before building the image.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
TARGET="models/local.gguf"
if [ -f "$TARGET" ]; then
  echo "already present: $TARGET ($(du -h "$TARGET" | cut -f1))"; exit 0
fi
URLS=(
  "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
  "https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
)
for u in "${URLS[@]}"; do
  echo ">> trying $u"
  if curl -L --fail --retry 3 --progress-bar -o "$TARGET.part" "$u"; then
    mv "$TARGET.part" "$TARGET"; break
  fi
done
if [ ! -f "$TARGET" ]; then
  echo "Direct download failed. Fallback:"
  echo "  pip install -U 'huggingface_hub[cli]'"
  echo "  huggingface-cli download unsloth/Qwen3-4B-Instruct-2507-GGUF --include '*Q4_K_M*' --local-dir models"
  echo "  mv models/*Q4_K_M*.gguf models/local.gguf"
  exit 1
fi
ls -lh "$TARGET"
