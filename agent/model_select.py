"""Runtime model selection from ALLOWED_MODELS (published on launch day —
never hardcoded; the rules invalidate submissions that call other models).

Ranks unknown model IDs by parsed parameter size, bans reasoning/thinking
models (their <think> tokens are billed as completion tokens and would wreck
the token score), and applies CATEGORY-CONDITIONAL routing:

  - hard escalations (math, logic, code_debug, code_generation)
        -> strongest allowed non-reasoning model (accuracy gate first)
  - language escalations (factual, ner, sentiment, summarization)
        -> a mid-size Gemma if one is allowed (keeps the "Best Use of Gemma
           via Fireworks" sub-prize in play without betting the accuracy
           gate on it), else the smallest capable mid-size model.
"""
import re

# Known families whose IDs don't carry a parseable size (total params, B).
KNOWN_SIZES = {
    "maverick": 400, "scout": 109, "kimi-k2": 1000, "kimi": 1000,
    "deepseek-v3": 671, "deepseek-v2": 236,
    "mixtral-8x7b": 47, "mixtral-8x22b": 141,
    "glm-4p5-air": 106, "glm-4p5": 355, "minimax": 456, "dbrx": 132,
}
_BAN_SUB = ("think", "reason", "gpt-oss", "magistral")
_BAN_TOK = {"r1", "qwq", "o1", "o3", "o4"}
# '4b' matches; 'a22b' (MoE active-param suffix) does not, thanks to (?<!a)
_SIZE = re.compile(r"(?<![\dxa])(\d+(?:\.\d+)?)b(?![a-z0-9])")
_MOE = re.compile(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)b")


def parse_allowed(raw):
    seen, out = set(), []
    for m in (raw or "").split(","):
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def is_banned(mid):
    s = (mid or "").lower()
    if any(k in s for k in _BAN_SUB):
        return True
    toks = set(re.split(r"[^a-z0-9]+", s))
    return bool(toks & _BAN_TOK)


def is_gemma(mid):
    return "gemma" in (mid or "").lower()


def size_of(mid):
    s = (mid or "").lower().split("/")[-1]
    for k, v in KNOWN_SIZES.items():
        if k in s:
            return float(v)
    sizes = [float(a) * float(b) for a, b in _MOE.findall(s)]
    sizes += [float(x) for x in _SIZE.findall(s)]
    return max(sizes) if sizes else 30.0


def choose(allowed):
    """Returns {'strong','language','all','gemma'} or {} if nothing allowed."""
    if not allowed:
        return {}
    usable = [m for m in allowed if not is_banned(m)]
    if not usable:
        # Only reasoning models allowed: must still comply — use them with
        # the hard max_tokens caps the router already applies.
        usable = list(allowed)
    by_size = sorted(usable, key=size_of)
    strong = by_size[-1]
    gemmas = sorted([m for m in usable if is_gemma(m)], key=size_of)
    big_gemmas = [m for m in gemmas if size_of(m) >= 10]
    if big_gemmas:
        language = big_gemmas[0]        # smallest Gemma >= ~10B
    elif gemmas and size_of(gemmas[-1]) >= 7:
        language = gemmas[-1]
    else:
        mids = [m for m in usable if 7 <= size_of(m) <= 90]
        language = sorted(mids, key=size_of)[0] if mids else strong
    return {"strong": strong, "language": language,
            "all": usable, "gemma": bool(gemmas)}
