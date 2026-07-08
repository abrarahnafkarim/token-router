"""Deterministic, zero-token task classifier for the 8 hackathon categories.

No LLM is used for routing: a remote LLM router would tax 100% of tasks with
tokens, and a local LLM router would burn the time budget. Regex/keyword rules
are free and deterministic. A misroute is not fatal: every category's prompt
still produces a reasonable answer, and verification/escalation catches bad
outputs.
"""
import re
from enum import Enum


class Cat(str, Enum):
    FACTUAL = "factual"
    MATH = "math"
    SENTIMENT = "sentiment"
    SUMMARY = "summarization"
    NER = "ner"
    DEBUG = "code_debug"
    CODEGEN = "code_generation"
    LOGIC = "logic"


_FENCE = re.compile(r"```")
_CODEY = re.compile(
    r"(\bdef\s+\w+\s*\(|\bclass\s+\w+\s*[:\(]|\bfunction\s+\w+\s*\(|\bimport\s+\w+"
    r"|#include\s*<|console\.log|System\.out|\bprint\s*\(|=>\s*\{|for\s+\w+\s+in\s+range\s*\()",
    re.M,
)
_DEBUG_W = re.compile(
    r"\b(bug(gy|s)?|debug|fix(es|ed)?|error|incorrect|wrong|broken|fail(s|ing|ed)?"
    r"|doesn'?t\s+work|not\s+work(ing)?|why\s+is\s+this|find\s+the\s+(bug|issue|problem)"
    r"|correct\s+(the|this|it))\b",
    re.I,
)
_GEN_W = re.compile(
    r"\b(write|implement|create|build|generate)\b[^.\n]{0,60}"
    r"\b(function|method|class|program|script|algorithm|code)\b",
    re.I,
)
_NER_W = re.compile(
    r"\bnamed\s+entit|\bentit(y|ies)\b|\bNER\b"
    r"|extract\b[^.\n]{0,80}\b(person|people|name|organi[sz]ation|compan(y|ies)|location|place|date)"
    r"|identify\b[^.\n]{0,80}\b(person|people|organi[sz]ation|location|date)",
    re.I,
)
_SENT_W = re.compile(
    r"\bsentiment\b"
    r"|\b(positive|negative|neutral)\b[^.\n]{0,50}\b(positive|negative|neutral)\b"
    r"|classif(y|ication)\b[^.\n]{0,60}\b(review|tweet|feedback|comment|opinion)",
    re.I,
)
_SUM_W = re.compile(
    r"\bsummar(y|ies|ise|ize|ised|ized|ising|izing|isation|ization)\b|\btl;?dr\b"
    r"|\bcondense\b|\bin\s+one\s+sentence\b",
    re.I,
)
_LOGIC_W = re.compile(
    r"\bpuzzle\b|\bdeduce\b|\bdeduction\b|\bconstraints?\b|\bexactly\s+one\b"
    r"|\bmust\s+be\s+true\b|\bknights?\b.{0,40}\bknaves?\b|\btruth[- ]?teller"
    r"|\bwho\s+(sits|sat|lives|owns|finished|came|is\s+(taller|older|younger|shorter))\b"
    r"|\b(left|right)\s+of\b|\bnext\s+to\b.{0,140}\bwho\b|\bseated\b|\bin\s+a\s+row\b"
    r"|\border\s+of\b.{0,60}\b(finish|arrival)",
    re.I | re.S,
)
_MATH_W = re.compile(
    r"%|\bpercent(age)?\b|\bcalculate\b|\bcompute\b|\bhow\s+(much|many|long|far)\b"
    r"|\btotal\b|\bsum\b|\baverage\b|\bcost\b|\bprice\b|\bprofit\b|\bdiscount\b"
    r"|\binterest\b|\brevenue\b|\bproject(ion|ed)?\b|\bper\s+(hour|day|week|month|year|unit)\b"
    r"|\bratio\b|\bspeed\b|\bkm/?h\b|\bmph\b|\brate\b",
    re.I,
)
_NUM = re.compile(r"\d")


def classify(prompt: str) -> Cat:
    p = prompt or ""
    has_code = bool(_FENCE.search(p)) or bool(_CODEY.search(p))

    if has_code and _DEBUG_W.search(p):
        return Cat.DEBUG
    if _GEN_W.search(p):
        return Cat.CODEGEN
    if _NER_W.search(p):
        return Cat.NER
    if _SENT_W.search(p):
        return Cat.SENTIMENT
    if _SUM_W.search(p):
        return Cat.SUMMARY
    if _LOGIC_W.search(p):
        return Cat.LOGIC
    if _MATH_W.search(p) and _NUM.search(p):
        return Cat.MATH
    if has_code:
        return Cat.DEBUG
    return Cat.FACTUAL
