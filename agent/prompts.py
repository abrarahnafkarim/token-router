"""Prompt templates. One builder for both paths.

Local tokens are free but cost wall-clock time; remote tokens cost leaderboard
rank. So every template is terse, single-shot, no system prompt, no few-shot
examples. Formats are chosen so the deterministic verifiers can check them.
"""
from .classifier import Cat
from .verifiers import parse_summary_constraint, prompt_wants_custom_format


def build(cat, prompt):
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
