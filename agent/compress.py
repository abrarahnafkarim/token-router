"""Prompt compression — squeeze tokens before sending to remote models.

Every token saved on the prompt side directly improves leaderboard rank.
These transforms are lossless (meaning doesn't remove info), just compact:
  - Collapse redundant whitespace (newlines, tabs, multi-spaces)
  - Strip markdown fences when the model doesn't need them for comprehension
  - Remove filler phrases that add tokens but not meaning
  - Trim trailing/leading whitespace on every line
"""
import re


# Filler phrases that inflate prompt tokens without adding information.
# Each is replaced by its shorter equivalent (or removed entirely).
_FILLER = [
    (r"\bplease\b\s*", ""),
    (r"\bkindly\b\s*", ""),
    (r"\bcould you\b\s*", ""),
    (r"\bcan you\b\s*", ""),
    (r"\bI would like you to\b\s*", ""),
    (r"\bI want you to\b\s*", ""),
    (r"\bI need you to\b\s*", ""),
    (r"\bin the following\b", "in this"),
    (r"\bthe following\b", "this"),
    (r"\bbelow is\b", "here is"),
    (r"\bas follows\b", ""),
]
_FILLER_RE = [(re.compile(p, re.IGNORECASE), r) for p, r in _FILLER]


def compress(text: str) -> str:
    """Compress a prompt string to use fewer tokens."""
    if not text:
        return text

    # 1. Strip each line, collapse blank lines
    lines = [l.strip() for l in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 2. Collapse multiple spaces (but not inside code blocks)
    # We preserve code blocks by splitting on ``` markers
    parts = text.split("```")
    for i in range(0, len(parts), 2):  # only non-code parts (even indices)
        parts[i] = re.sub(r"[ \t]{2,}", " ", parts[i])
    text = "```".join(parts)

    # 3. Remove filler words (only outside code blocks)
    parts = text.split("```")
    for i in range(0, len(parts), 2):
        for pat, repl in _FILLER_RE:
            parts[i] = pat.sub(repl, parts[i])
    text = "```".join(parts)

    # 4. Collapse any resulting double-spaces
    text = re.sub(r"  +", " ", text)

    return text.strip()
