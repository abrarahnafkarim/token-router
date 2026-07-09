"""Offline dry run: exercises the entire pipeline with a FAKE local model and
a FAKE Fireworks client, so it runs anywhere (no GGUF, no network, no creds).

Covers the evaluation fixes explicitly:
  - MATH/LOGIC agreement gate (disagreeing samples must escalate)
  - category-conditional model pick (hard->strong, language->gemma)
  - reasoning-model ban and MoE size parsing
  - verifiers (NER json, summary length, code ast.parse, debug-unchanged)
  - deadline flush path
Run: python3 tests/dry_run.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.classifier import Cat, classify
from agent import verifiers as V
from agent.model_select import choose, parse_allowed, is_banned, size_of
from agent.deadline import Deadline
from agent.router import Router

FAILS = []


def check(name, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


# ----------------------------------------------------------- classifier
def test_classifier():
    print("[classifier]")
    cases = {
        "What is the capital of France?": Cat.FACTUAL,
        "A shirt costs 1200 after a 20% discount. Original price?": Cat.MATH,
        "Classify the sentiment of this tweet: I love it": Cat.SENTIMENT,
        "Summarise the following text in one sentence: ...": Cat.SUMMARY,
        "Extract the named entities (person, organization) from: Alice at Acme": Cat.NER,
        "Write a Python function is_prime(n) that returns True if prime": Cat.CODEGEN,
        "This code has a bug, fix it:\n```python\ndef f():\n  return 1/0\n```": Cat.DEBUG,
        "Alice finished before Bob. Carol before Bob. Who finished last?": Cat.LOGIC,
    }
    for p, want in cases.items():
        got = classify(p)
        check(f"{want.value:14s} <- {p[:42]!r}", got == want)


# ----------------------------------------------------------- verifiers
def test_verifiers():
    print("[verifiers]")
    ok, fixed = V.verify(Cat.MATH, "Steps: 720/0.6 = 1200.\nAnswer: 1200", "orig price?")
    check("math accepts numeric final", ok and "1200" in fixed)
    ok, _ = V.verify(Cat.MATH, "I'm not sure about this one", "x?")
    check("math rejects hedge", not ok)

    ok, fixed = V.verify(Cat.SENTIMENT,
                         "Sentiment: positive\nReason: the reviewer praises battery and screen",
                         "classify sentiment")
    check("sentiment normalizes", ok and fixed.lower().startswith("sentiment: positive"))
    ok, _ = V.verify(Cat.SENTIMENT, "It is good", "classify sentiment")
    check("sentiment rejects missing label", not ok)

    ok, body = V.verify(Cat.SUMMARY, "This is a five word summary", "summarise in 10 words")
    check("summary within word limit", ok)
    ok, _ = V.verify(Cat.SUMMARY, "one two three four five six", "summarise in 3 words")
    check("summary rejects over limit", not ok)

    ner = '{"person":["Alice"],"organization":["Acme Corp"],"location":["Paris"],"date":["March 5, 2024"]}'
    ok, fixed = V.verify(Cat.NER, ner, "extract entities person organization location date")
    check("ner accepts good json", ok and "Acme" in fixed)
    ok, fixed = V.verify(Cat.NER,
                         '[{"type":"person","text":"Alice"},{"type":"org","text":"Acme"}]',
                         "extract entities")
    check("ner accepts list-of-dicts + alias", ok and "Alice" in fixed)
    ok, _ = V.verify(Cat.NER, "Alice works at Acme in Paris", "extract entities")
    check("ner rejects prose", not ok)

    good = "```python\ndef is_prime(n):\n    return n > 1 and all(n%i for i in range(2,int(n**0.5)+1))\n```"
    ok, _ = V.verify(Cat.CODEGEN, good, "write a function is_prime(n)")
    check("codegen accepts valid+named", ok)
    ok, _ = V.verify(Cat.CODEGEN, "```python\ndef woops(:\n```", "write is_prime")
    check("codegen rejects syntax error", not ok)
    ok, _ = V.verify(Cat.CODEGEN, "```python\ndef other(x):\n    return x\n```",
                     "write a function is_prime(n)")
    check("codegen rejects wrong function name", not ok)

    buggy = "```python\ndef average(nums):\n    total=0\n    for x in nums: total+=x\n    return total/(len(nums)-1)\n```"
    ok, _ = V.verify(Cat.DEBUG, buggy, "fix this bug:\n" + buggy)
    check("debug rejects unchanged buggy code", not ok)
    fixed_code = "Bug: off-by-one in divisor\n```python\ndef average(nums):\n    return sum(nums)/len(nums)\n```"
    ok, _ = V.verify(Cat.DEBUG, fixed_code, "fix this bug:\n" + buggy)
    check("debug accepts corrected code", ok)


# ----------------------------------------------------------- agreement
def test_agreement():
    print("[agreement — the accuracy-gate guard]")
    check("math agrees on same number",
          V.agree(Cat.MATH, "Answer: 1200", "reasoning...\nAnswer: 1200.0"))
    check("math escalates on disagreement",
          not V.agree(Cat.MATH, "Answer: 1200", "Answer: 900"))
    check("logic agrees on same text",
          V.agree(Cat.LOGIC, "Answer: Bob", "so the last is Bob\nAnswer: Bob"))
    check("logic escalates on disagreement",
          not V.agree(Cat.LOGIC, "Answer: Bob", "Answer: Alice"))


# ----------------------------------------------------------- model select
def test_model_select():
    print("[model_select]")
    check("bans deepseek-r1", is_banned("accounts/fireworks/models/deepseek-r1"))
    check("bans qwq", is_banned("accounts/fireworks/models/qwq-32b"))
    check("bans gpt-oss", is_banned("accounts/fireworks/models/gpt-oss-120b"))
    check("allows gemma-3-27b", not is_banned("accounts/fireworks/models/gemma-3-27b-it"))
    check("moe size 8x22b ~ 141-176", 130 <= size_of("mixtral-8x22b-instruct") <= 200)
    check("qwen3-4b size ~4", 3.5 <= size_of("accounts/fireworks/models/qwen3-4b-instruct") <= 4.5)
    check("a22b active-suffix ignored -> uses known/base",
          size_of("qwen3-235b-a22b") >= 200)

    allowed = ("accounts/fireworks/models/gemma-3-27b-it,"
               "accounts/fireworks/models/llama-v3p3-70b-instruct,"
               "accounts/fireworks/models/qwen3-4b-instruct,"
               "accounts/fireworks/models/deepseek-r1")
    sel = choose(parse_allowed(allowed))
    check("strong = 70b (not banned r1)", "70b" in sel["strong"])
    check("language = gemma (sub-prize)", "gemma" in sel["language"])
    check("r1 excluded from usable", all("r1" not in m for m in sel["all"]))
    check("gemma flag set", sel["gemma"] is True)

    sel2 = choose(parse_allowed("accounts/fireworks/models/llama-v3p1-8b-instruct"))
    check("single-model fallback ok", sel2["strong"] == sel2["language"])


# ----------------------------------------------------------- fakes + router
class FakeLocal:
    ok = True
    tps = 20.0
    pp = 120.0

    def __init__(self, answers, disagree_math=False):
        self.answers = answers
        self.disagree_math = disagree_math
        self.calls = 0

    def estimate(self, p, g):
        return 0.05

    def gen(self, user, max_tokens, temperature=0.0):
        self.calls += 1
        cat = self.answers.get("_cat")
        # simulate math disagreement between t=0 and t=0.7 samples
        if self.disagree_math and "Answer:" in user and temperature > 0:
            return "Answer: 999999"
        for key, val in self.answers.items():
            if key != "_cat" and key in user:
                return val
        return self.answers.get("_default", "Answer: 42")


class FakeFW:
    enabled = True

    def __init__(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.errors = 0
        self.log = []

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    def chat(self, model, user, max_tokens=128, temperature=0.0,
             stop=None, json_mode=False, system=None):
        self.calls += 1
        self.prompt_tokens += 20
        self.completion_tokens += 10
        self.log.append(model)
        if "is_prime" in user:
            return "```python\ndef is_prime(n):\n    return n>1 and all(n%i for i in range(2,int(n**0.5)+1))\n```"
        if json_mode or "person" in user.lower():
            return '{"person":["Alice"],"organization":["Acme Corp"],"location":["Paris"],"date":["March 5, 2024"]}'
        return "Answer: remote-result"


def test_router_local_path():
    print("[router — local success path, zero remote tokens]")
    tasks = [
        {"task_id": "a", "prompt": "What is the capital of Bangladesh?"},
        {"task_id": "b", "prompt": "Summarise in one sentence: The cat sat on the mat."},
    ]
    local = FakeLocal({
        "capital of Bangladesh": "The capital of Bangladesh is Dhaka.",
        "Summarise": "The cat sat on the mat.",
    })
    fw = FakeFW()
    sel = choose(parse_allowed("accounts/fireworks/models/gemma-3-27b-it"))

    class C:
        force_remote = False; remote_cats = set(); local_ctx = 8192; remote_workers = 2
    r = Router(C(), local, fw, sel, Deadline(575, 30))
    out = r.solve_all(tasks)
    check("both answered", len(out) == 2 and all(out.values()))
    check("zero remote tokens (all local)", fw.total_tokens == 0)


def test_router_escalation():
    print("[router — math disagreement forces escalation]")
    tasks = [{"task_id": "m", "prompt": "A shirt costs 720 after a 40% discount. Original price?"}]
    local = FakeLocal({"_default": "Answer: 1200"}, disagree_math=True)
    fw = FakeFW()
    sel = choose(parse_allowed(
        "accounts/fireworks/models/gemma-3-27b-it,accounts/fireworks/models/llama-v3p3-70b-instruct"))

    class C:
        force_remote = False; remote_cats = set(); local_ctx = 8192; remote_workers = 2
    r = Router(C(), local, fw, sel, Deadline(575, 30))
    out = r.solve_all(tasks)
    check("math task answered", bool(out.get("m")))
    check("escalated to remote (disagreement)", fw.calls == 1)
    check("hard category used STRONG model", "gemma-4-31b-it-nvfp4" in fw.log[0])


def test_router_force_remote():
    print("[router — FORCE_REMOTE (Architecture B)]")
    tasks = [
        {"task_id": "x", "prompt": "Extract entities person org location date: Alice at Acme in Paris on March 5, 2024"},
        {"task_id": "y", "prompt": "Write a Python function is_prime(n)"},
    ]
    fw = FakeFW()
    sel = choose(parse_allowed(
        "accounts/fireworks/models/gemma-3-27b-it,accounts/fireworks/models/llama-v3p3-70b-instruct"))

    class C:
        force_remote = True; remote_cats = set(); local_ctx = 8192; remote_workers = 2
    r = Router(C(), None, fw, sel, Deadline(575, 30))
    out = r.solve_all(tasks)
    check("both answered via remote", len(out) == 2 and all(out.values()))
    check("NER (language) routed to gemma", "gemma-4-26b-a4b-it" in fw.log[0])
    check("codegen (hard) routed to minimax-m3", "minimax-m3" in fw.log[1])


def main():
    for t in (test_classifier, test_verifiers, test_agreement, test_model_select,
              test_router_local_path, test_router_escalation, test_router_force_remote):
        t()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): " + "; ".join(FAILS))
        sys.exit(1)
    print("ALL DRY-RUN CHECKS PASSED")


if __name__ == "__main__":
    main()
