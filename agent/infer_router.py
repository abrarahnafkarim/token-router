"""Loads the fine-tuned DistilBERT router and predicts easy/hard for a prompt.

This never calls Fireworks - it's a local forward pass, so it costs zero
tokens under the hackathon's scoring rules. That's the entire point of
fine-tuning a router instead of asking an LLM to classify difficulty.
"""
from pathlib import Path

import torch
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

# The checkpoint is built into the image at /app/models/router-distilbert
CHECKPOINT_DIR = Path("/app/models/router-distilbert")

_model = None
_tokenizer = None
_device = None


def _load():
    global _model, _tokenizer, _device
    if _model is not None:
        return
    _device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
    _tokenizer = DistilBertTokenizerFast.from_pretrained(CHECKPOINT_DIR)
    _model = DistilBertForSequenceClassification.from_pretrained(CHECKPOINT_DIR).to(_device)
    _model.eval()


# ── Three-tier confidence thresholds ──
# hard_prob < EASY_CEIL  → "easy"      — safe for local model, 0 remote tokens
# EASY_CEIL ≤ hard_prob < HARD_FLOOR → "uncertain" — local attempt, but verify
# hard_prob ≥ HARD_FLOOR → "hard"      — skip local, go straight to remote
EASY_CEIL  = 0.30
HARD_FLOOR = 0.65


def predict(prompt: str) -> str:
    """Returns "easy", "uncertain", or "hard"."""
    _load()
    enc = _tokenizer(prompt, truncation=True, padding=True, max_length=256, return_tensors="pt").to(_device)
    with torch.no_grad():
        logits = _model(**enc).logits
    probs = torch.softmax(logits, dim=-1)
    hard_prob = probs[0, 1].item()
    if hard_prob >= HARD_FLOOR:
        return "hard"
    if hard_prob >= EASY_CEIL:
        return "uncertain"
    return "easy"


def confidence(prompt: str) -> float:
    """Returns raw probability the prompt is 'hard' (0.0–1.0)."""
    _load()
    enc = _tokenizer(prompt, truncation=True, padding=True, max_length=256, return_tensors="pt").to(_device)
    with torch.no_grad():
        logits = _model(**enc).logits
    return torch.softmax(logits, dim=-1)[0, 1].item()


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What is 2 + 2?"
    print(f"label={predict(q)}  hard_prob={confidence(q):.3f}")

