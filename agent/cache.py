"""Semantic similarity cache — reuse answers for near-duplicate prompts.

Uses the DistilBERT model (already loaded for routing) to compute embeddings.
If an incoming prompt is ≥95% cosine-similar to a previously answered one,
the cached answer is returned instantly for zero tokens.

In a 19-task evaluation, this is a safety net: if two tasks are rephrased
versions of each other, we avoid paying remote tokens twice.
"""
try:
    import torch
except ImportError:
    torch = None


_cache = []  # list of (embedding_tensor, answer_string)
SIMILARITY_THRESHOLD = 0.95


def _get_embedding(prompt: str):
    """Get the [CLS] embedding from the router's DistilBERT model."""
    if torch is None:
        return None
    try:
        from .infer_router import _load, _model, _tokenizer, _device
        _load()
        enc = _tokenizer(prompt, truncation=True, padding=True,
                         max_length=256, return_tensors="pt").to(_device)
        with torch.no_grad():
            outputs = _model.distilbert(**enc)
        # [CLS] token embedding is the first token
        cls = outputs.last_hidden_state[:, 0, :]
        # Normalize for cosine similarity
        return cls / cls.norm(dim=-1, keepdim=True)
    except Exception:
        return None


def lookup(prompt: str):
    """Check if a similar prompt was already answered. Returns answer or None."""
    emb = _get_embedding(prompt)
    if emb is None:
        return None
    for cached_emb, cached_answer in _cache:
        sim = torch.nn.functional.cosine_similarity(emb, cached_emb).item()
        if sim >= SIMILARITY_THRESHOLD:
            return cached_answer
    return None


def store(prompt: str, answer: str):
    """Cache a prompt→answer pair for future lookups."""
    if not answer:
        return
    emb = _get_embedding(prompt)
    if emb is not None:
        _cache.append((emb, answer))
