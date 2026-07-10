"""Prompt templates — separate builders for local and remote paths.

Local tokens are free but cost wall-clock time; remote tokens cost leaderboard
rank. So remote templates are terse, single-shot, no few-shot examples.
Local templates include 1-2 few-shot examples per category to boost accuracy
on borderline questions — these tokens are invisible to the leaderboard.
"""
from .classifier import Cat
from .verifiers import parse_summary_constraint, prompt_wants_custom_format


# ── Few-shot examples for the local model (free tokens) ──
_FEW_SHOT = {
    Cat.MATH: (
        "Example:\n"
        "Q: An item costs $50. It has a 20% discount, then 10% tax on the discounted price. Final price?\n"
        "A: Discounted: $50 × 0.80 = $40. Tax: $40 × 0.10 = $4. Total: $44.\n"
        "Answer: 44.00\n\n"
    ),
    Cat.LOGIC: (
        "Example:\n"
        "Q: Three friends each own a different pet: cat, dog, fish. Ana doesn't own the dog. Ben doesn't own the fish. Cleo owns the cat. Who owns the dog?\n"
        "A: Cleo owns the cat. Ben doesn't own the fish, so Ben owns the dog. Ana owns the fish.\n"
        "Answer: Ben\n\n"
    ),
    Cat.SENTIMENT: (
        "Example:\n"
        "Q: Classify the sentiment: \"The app crashed three times during checkout and support never responded.\"\n"
        "A:\nSentiment: negative\nReason: Repeated crashes and unresponsive support indicate a poor experience.\n\n"
    ),
    Cat.DEBUG: (
        "Example:\n"
        "Q: Find the bug:\n```python\ndef is_even(n):\n    if n % 2 == 1:\n        return True\n    return False\n```\n"
        "A: Bug: The condition is inverted — n % 2 == 1 means odd, not even.\n```python\ndef is_even(n):\n    if n % 2 == 0:\n        return True\n    return False\n```\n\n"
    ),
    Cat.SUMMARY: (
        "Example:\n"
        "Q: Summarize in one sentence: The city council approved a new bike lane network covering 12 miles. Construction begins next spring.\n"
        "A: The city council approved a 12-mile bike lane network with construction starting next spring.\n\n"
    ),
    Cat.CODEGEN: (
        "Example:\n"
        "Q: Write a Python function `is_palindrome(s)` that returns True if s reads the same forwards and backwards (ignore case).\n"
        "A:\n```python\ndef is_palindrome(s):\n    s = s.lower()\n    return s == s[::-1]\n```\n\n"
    ),
}


def build(cat, prompt):
    """Terse prompt for remote models — every token counts on the leaderboard."""
    p = (prompt or "").strip()
    if cat == Cat.FACTUAL:
        return f"{p}\n\nAnswer directly and concisely in 1-3 sentences. No preamble."
    if cat == Cat.MATH:
        return f"{p}\n\nSolve with brief steps. Final line must be exactly: Answer: <number>"
    if cat == Cat.SENTIMENT:
        return (f"{p}\n\nReply in exactly this format:\n"
                "Sentiment: <positive|negative|neutral>\nReason: <one short sentence>")
    if cat == Cat.SUMMARY:
        return (f"{p}\n\nOutput only the summary, nothing else. "
                "Obey the stated length/format limit exactly.")
    if cat == Cat.NER:
        if prompt_wants_custom_format(p):
            return f"{p}\n\nOutput only the entities in the requested format, nothing else."
        return (f"{p}\n\nReturn only compact JSON in exactly this shape, filled from the text: "
                '{"person":[],"organization":[],"location":[],"date":[]}')
    if cat == Cat.CODEGEN:
        return f"{p}\n\nOutput only the code. No explanation."
    if cat == Cat.DEBUG:
        return f"{p}\n\nFirst line: Bug: <one short line>. Then output only the corrected code."
    if cat == Cat.LOGIC:
        return (f"{p}\n\nThink step by step briefly. "
                "Final line must be exactly: Answer: <your answer>")
    return p


def build_local(cat, prompt):
    """Enriched prompt for the local model — free tokens, more context = better accuracy."""
    few = _FEW_SHOT.get(cat, "")
    base = build(cat, prompt)
    if few:
        return f"{few}Now answer this:\n{base}"
    return base


def max_tokens_for(cat, prompt, base):
    """Summaries get a cap derived from the task's own stated limit."""
    if cat == Cat.SUMMARY:
        kind, n = parse_summary_constraint(prompt)
        if kind == "words":
            return min(420, int(n * 1.8) + 24)
        if kind == "sentences":
            return min(300, 60 * n + 30)
        if kind == "chars":
            return min(300, n // 3 + 24)
        return 150
    return base

