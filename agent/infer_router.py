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


# Confidence threshold: only classify as "hard" when the model is at least
# this confident.  Raising this reduces false-positives (easy prompts sent
# to the expensive remote model, wasting tokens) at the cost of potentially
# missing some genuinely hard prompts.  0.65 is a good balance: the training
# metrics showed recall=1.0 / precision=0.20, so we can afford to tighten.
HARD_THRESHOLD = 0.65


def predict(prompt: str) -> str:
    """Returns "easy" or "hard" using confidence-based thresholding."""
    _load()
    enc = _tokenizer(prompt, truncation=True, padding=True, max_length=256, return_tensors="pt").to(_device)
    with torch.no_grad():
        logits = _model(**enc).logits
    probs = torch.softmax(logits, dim=-1)
    hard_prob = probs[0, 1].item()     # probability of "hard"
    return "hard" if hard_prob >= HARD_THRESHOLD else "easy"


if __name__ == "__main__":
    import sys
    print(predict(sys.argv[1] if len(sys.argv) > 1 else "What is 2 + 2?"))
