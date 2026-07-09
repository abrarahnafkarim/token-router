"""Zero-cost deterministic verifiers + agreement checks.

Design principle (from the evaluation of the original plan): a verifier must
never be able to bless a *wrongly set up* answer. Arithmetic recomputation of
the model's own expression can't catch a wrong setup, so MATH and LOGIC use
AGREEMENT between two independent local samples (t=0.0 and t=0.7) instead —
if the model can't reproduce its own final answer under sampling noise, the
answer is not trusted and the task escalates. Everything else uses hard
programmatic checks (JSON schema, length constraints, ast.parse, name checks).
"""
import ast
import json
import re

HEDGES = (
    "i don't know", "i do not know", "cannot answer", "can't answer",
    "i'm not sure", "i am not sure", "as an ai", "insufficient information",
    "unable to determine",
)
NUM_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")
ANS_LINE = re.compile(r"answer\s*[:=\-]\s*(.+)", re.I)
_STOPNAMES = {"that", "which", "to", "for", "in", "named", "called", "the", "a", "an"}

CANON = ("person", "organization", "location", "date")
ALIASES = {
    "people": "person", "persons": "person", "names": "person", "name": "person",
    "per": "person",
    "org": "organization", "orgs": "organization", "organizations": "organization",
    "organisation": "organization", "organisations": "organization",
    "company": "organization", "companies": "organization",
    "locations": "location", "place": "location", "places": "location", "gpe": "location",
    "loc": "location", "dates": "date", "time": "date",
}


# ---------------------------------------------------------------- helpers
def _final_segment(text):
    m = None
    for m in ANS_LINE.finditer(text or ""):
        pass
    return m.group(1).strip() if m else None


def final_number(text):
    seg = _final_segment(text)
    for source in ([seg] if seg else []) + [text or ""]:
        if not source:
            continue
        nums = NUM_RE.findall(source)
        if nums:
            s = nums[-1].replace(",", "").replace("$", "").rstrip("%").strip()
            try:
                return float(s)
            except ValueError:
                continue
    return None


def numbers_close(a, b, rel=1e-4):
    if a is None or b is None:
        return False
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def fmt_num(x):
    if x is None:
        return ""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.4f}".rstrip("0").rstrip(".")


def extract_code(text):
    t = text or ""
    m = re.search(r"```[a-zA-Z0-9]*[ \t]*\n(.*?)```", t, re.S)
    if m:
        return m.group(1).strip()
    if "```" in t:  # unterminated fence
        m = re.search(r"```[a-zA-Z0-9]*[ \t]*\n?(.*)", t, re.S)
        if m:
            return m.group(1).strip()
    return t.strip()


def looks_python(prompt, code):
    if re.search(r"\bpython\b", prompt or "", re.I):
        return True
    return bool(re.search(
        r"^\s*(def |import |from \w+ import|class \w+|for .+ in .+:|if .+:)",
        code or "", re.M))


def python_ok(code):
    try:
        ast.parse(code)
        return True
    except Exception:
        return False


def fn_name_from_prompt(prompt):
    p = prompt or ""
    for pat in (
        r"function\s+(?:called\s+|named\s+)?[`'\"]?([A-Za-z_]\w*)[`'\"]?\s*\(",
        r"function\s+(?:called\s+|named\s+)[`'\"]?([A-Za-z_]\w*)",
        r"[`'\"]([A-Za-z_]\w*)\s*\(",
        r"\bdef\s+([A-Za-z_]\w*)",
    ):
        m = re.search(pat, p)
        if m and m.group(1).lower() not in _STOPNAMES:
            return m.group(1)
    return None


def _sentences(t):
    return [s for s in re.split(r"[.!?]+(?:\s|$)", (t or "").strip()) if s.strip()]


def parse_summary_constraint(prompt):
    p = (prompt or "").lower()
    m = re.search(
        r"(?:in|to|within|of|under|at\s+most|no\s+more\s+than|maximum\s+of|max(?:imum)?)"
        r"\s+(\d+)\s+words?", p)
    if m:
        return ("words", int(m.group(1)))
    if re.search(r"\b(one|a\s+single|1)\s+sentence\b", p):
        return ("sentences", 1)
    m = re.search(r"\b(two|three|four|2|3|4)\s+sentences?\b", p)
    if m:
        w = m.group(1)
        return ("sentences", {"two": 2, "three": 3, "four": 4}.get(w) or int(w))
    m = re.search(
        r"(?:under|at\s+most|no\s+more\s+than|within|max(?:imum)?(?:\s+of)?)"
        r"\s+(\d+)\s+characters", p)
    if m:
        return ("chars", int(m.group(1)))
    if "bullet" in p:
        return ("bullets", None)
    return (None, None)


def prompt_wants_custom_format(prompt):
    return bool(re.search(
        r"\b(as\s+a\s+table|as\s+a\s+list|bullet|comma[- ]separated|csv"
        r"|one\s+per\s+line|in\s+the\s+format)\b", prompt or "", re.I))


def parse_json_lenient(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = extract_code(t)
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = t.find(opener), t.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                continue
    return None


# ---------------------------------------------------------------- NER
def verify_ner(a, prompt):
    if prompt_wants_custom_format(prompt) and not re.search(r"\bjson\b", prompt, re.I):
        return (len((a or "").strip()) >= 2), (a or "").strip()
    obj = parse_json_lenient(a)
    out = {k: [] for k in CANON}
    if obj is None:
        return False, a
    if isinstance(obj, list):
        for it in obj:
            if isinstance(it, dict):
                ty = str(it.get("type") or it.get("label") or "").lower()
                ty = ALIASES.get(ty, ty)
                tx = it.get("text") or it.get("entity") or it.get("name") or it.get("value")
                if ty in out and tx:
                    out[ty].append(str(tx))
        if any(out.values()):
            return True, json.dumps(out, separators=(",", ":"))
        return False, a
    if isinstance(obj, dict):
        matched = False
        for k, v in obj.items():
            ck = ALIASES.get(str(k).lower(), str(k).lower())
            if ck in out:
                matched = True
                if isinstance(v, list):
                    out[ck] = [str(x) for x in v if isinstance(x, (str, int, float))][:25]
                elif isinstance(v, str) and v.strip():
                    out[ck] = [v.strip()]
        if matched:
            return True, json.dumps(out, separators=(",", ":"))
    return False, a


# ---------------------------------------------------------------- main verify
def verify(cat, ans, prompt):
    """Returns (ok, normalized_answer)."""
    from .classifier import Cat
    a = (ans or "").strip()
    if not a:
        return False, a
    low = a.lower()
    if any(h in low for h in HEDGES):
        return False, a

    if cat == Cat.FACTUAL:
        return (len(a) >= 2), a

    if cat == Cat.MATH:
        n = final_number(a)
        if n is None:
            return False, a
        if not ANS_LINE.search(a):
            a = f"{a}\nAnswer: {fmt_num(n)}"
        return True, a

    if cat == Cat.SENTIMENT:
        m = re.search(r"\b(positive|negative|neutral)\b", low)
        if not m:
            return False, a
        label = m.group(1)
        rm = re.search(r"reason\s*[:\-]\s*(.+)", a, re.I | re.S)
        reason = rm.group(1).strip() if rm else re.sub(
            r"(?i)sentiment\s*[:\-]?\s*(positive|negative|neutral)[.,]?\s*", "", a).strip()
        reason = reason.split("\n")[0].strip()
        if len(reason) < 8:
            return False, a
        if not reason.endswith((".", "!", "?")):
            reason += "."
        return True, f"Sentiment: {label}. Reason: {reason}"

    if cat == Cat.SUMMARY:
        kind, n = parse_summary_constraint(prompt)
        body = re.sub(r"(?i)^\s*summary\s*[:\-]\s*", "", a).strip()
        # Strip meta-commentary patterns from models that echo instructions
        body = re.sub(
            r"(?i)^(we need|let'?s|need to|i need|let me|i will|here is|here's|the summary is)[^\n]*?[.:]\s*",
            "", body).strip()
        # Extract quoted summary if present
        qm = re.search(r'"([^"]{8,})"', body)
        if qm:
            body = qm.group(1).strip()
        # Strip trailing meta like "Count: ..." or "Word count: ..."
        body = re.sub(r"\s*(?:Count|Word count|Words?)\s*[:=].*$", "", body,
                      flags=re.I | re.S).strip()
        if kind == "words" and len(body.split()) > n:
            return False, body
        if kind == "sentences" and len(_sentences(body)) > n:
            return False, body
        if kind == "chars" and len(body) > n:
            return False, body
        if kind == "bullets" and not re.search(r"(?m)^\s*[-*\u2022]", body):
            return False, body
        return True, body

    if cat == Cat.NER:
        return verify_ner(a, prompt)

    if cat == Cat.CODEGEN:
        code = extract_code(a)
        if not code:
            return False, a
        if looks_python(prompt, code) and not python_ok(code):
            return False, a
        name = fn_name_from_prompt(prompt)
        if name and name not in code:
            return False, a
        return True, a

    if cat == Cat.DEBUG:
        body = re.sub(r"(?im)^\s*bug\s*:.*?$", "", a, count=1)
        code = extract_code(body)
        if not code:
            return False, a
        orig = extract_code(prompt)
        if orig and code.strip() == orig.strip():
            return False, a  # returned the buggy code unchanged
        if looks_python(prompt, code) and not python_ok(code):
            return False, a
        return True, a

    if cat == Cat.LOGIC:
        seg = _final_segment(a)
        if not seg or len(seg) > 240:
            return False, a
        return True, a

    return True, a


# ---------------------------------------------------------------- agreement
def norm_answer(t):
    seg = _final_segment(t) or (t or "").strip().split("\n")[-1]
    seg = re.sub(r"[^a-z0-9 ]", " ", seg.lower())
    seg = re.sub(r"\b(the|a|an|is|are|was|were|it|its)\b", " ", seg)
    return " ".join(seg.split())


def agree(cat, a1, a2):
    """Two independent samples must reproduce the same final answer.
    This is the accuracy-gate guard for MATH and LOGIC: it catches wrong
    problem setups that expression-recomputation would happily confirm."""
    from .classifier import Cat
    if cat == Cat.MATH:
        return numbers_close(final_number(a1), final_number(a2))
    n1, n2 = norm_answer(a1), norm_answer(a2)
    if not n1 or not n2:
        return False
    return n1 == n2 or n1 in n2 or n2 in n1
