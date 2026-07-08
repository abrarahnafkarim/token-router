"""Dev-set generator + judge for the empirical measurement loop.

Generates a synthetic tasks.json across all 8 categories with programmatically
checkable ground truth, so you can measure per-category local accuracy,
escalation rate, and remote-token cost BEFORE burning leaderboard submissions.

Usage:
  python3 tests/make_devset.py                 # -> tests/generated/tasks.json + truth.json
  # run the agent on it (Docker or local), producing output/results.json, then:
  python3 tests/make_devset.py --judge output/results.json

The judge is deterministic where possible (math numbers, sentiment labels, NER
entities, code execution) and falls back to substring/keyword checks for
factual/summary/logic. It is a rough proxy for the hackathon's LLM-Judge, not a
substitute — use it to compare configurations, not to predict the exact gate.
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.verifiers import final_number, numbers_close, extract_code, parse_json_lenient

random.seed(7)
OUT_DIR = os.path.join(os.path.dirname(__file__), "generated")

CAPITALS = {"France": "Paris", "Japan": "Tokyo", "Bangladesh": "Dhaka",
            "Brazil": "Brasilia", "Egypt": "Cairo", "Canada": "Ottawa",
            "Kenya": "Nairobi", "Norway": "Oslo"}
ELEMENTS = {"gold": "Au", "iron": "Fe", "sodium": "Na", "oxygen": "O",
            "hydrogen": "H", "carbon": "C"}


def gen_factual():
    tasks, truth = [], []
    for c, cap in CAPITALS.items():
        tasks.append(f"What is the capital of {c}?")
        truth.append({"kind": "contains", "value": cap})
    for e, sym in ELEMENTS.items():
        tasks.append(f"What is the chemical symbol for {e}?")
        truth.append({"kind": "contains", "value": sym})
    return tasks, truth


def gen_math():
    tasks, truth = [], []
    for _ in range(10):
        price = random.randint(200, 2000)
        disc = random.choice([10, 20, 25, 40, 50])
        paid = round(price * (1 - disc / 100), 2)
        tasks.append(f"A jacket costs {paid} taka after a {disc}% discount. "
                     f"What was the original price in taka?")
        truth.append({"kind": "number", "value": float(price)})
    for _ in range(6):
        a, b, c = (random.randint(2, 40) for _ in range(3))
        tasks.append(f"Compute {a} * {b} + {c}.")
        truth.append({"kind": "number", "value": float(a * b + c)})
    return tasks, truth


POS = ["The battery lasts two full days and the screen is gorgeous.",
       "Fast delivery and the product exceeded my expectations.",
       "Absolutely love it, best purchase this year."]
NEG = ["The item arrived broken and support ignored my emails.",
       "Terrible quality, it stopped working after a day.",
       "Overpriced and painfully slow, very disappointed."]
NEU = ["The package arrived on Tuesday in a brown box.",
       "It is a phone with a charger and a manual included.",
       "The meeting was rescheduled to next week."]


def gen_sentiment():
    tasks, truth = [], []
    for txt, lab in ([(t, "positive") for t in POS] + [(t, "negative") for t in NEG]
                     + [(t, "neutral") for t in NEU]):
        tasks.append(f"Classify the sentiment of this review as positive, negative, "
                     f"or neutral and justify: '{txt}'")
        truth.append({"kind": "label", "value": lab})
    return tasks, truth


def gen_summary():
    text = ("Photosynthesis is the process by which green plants convert sunlight into "
            "chemical energy. Chlorophyll in the chloroplasts absorbs light, splitting "
            "water and combining carbon dioxide into glucose, releasing oxygen.")
    tasks, truth = [], []
    for n in (8, 12, 20):
        tasks.append(f"Summarise the following text in at most {n} words: {text}")
        truth.append({"kind": "wordmax", "value": n, "must": ["photosynthesis"]})
    tasks.append(f"Summarise the following text in one sentence: {text}")
    truth.append({"kind": "sentmax", "value": 1, "must": ["photosynthesis"]})
    return tasks, truth


def gen_ner():
    rows = [
        ("Alice, the CEO of Acme Corp, met investors in Paris on March 5, 2024.",
         {"person": ["Alice"], "organization": ["Acme Corp"],
          "location": ["Paris"], "date": ["March 5, 2024"]}),
        ("Dr. Rahman joined BRAC University in Dhaka in January 2021.",
         {"person": ["Rahman"], "organization": ["BRAC University"],
          "location": ["Dhaka"], "date": ["January 2021"]}),
    ]
    tasks, truth = [], []
    for sent, ents in rows:
        tasks.append(f"Extract the named entities (person, organization, location, "
                     f'date) as JSON from: "{sent}"')
        truth.append({"kind": "ner", "value": ents})
    return tasks, truth


def gen_codegen():
    specs = [
        ("is_prime", "Write a Python function is_prime(n) that returns True if n is prime.",
         [(2, True), (3, True), (4, False), (17, True), (1, False), (0, False)]),
        ("factorial", "Write a Python function factorial(n) returning n! for n>=0.",
         [(0, 1), (1, 1), (5, 120), (3, 6)]),
        ("reverse_string", "Write a Python function reverse_string(s) that returns s reversed.",
         [("abc", "cba"), ("", ""), ("x", "x")]),
    ]
    tasks, truth = [], []
    for name, prompt, cases in specs:
        tasks.append(prompt)
        truth.append({"kind": "code", "fn": name, "cases": cases})
    return tasks, truth


def gen_debug():
    items = [
        ("def average(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total / (len(nums) - 1)",
         "average", [([2, 4, 6], 4.0), ([10], 10.0)]),
        ("def maximum(a, b):\n    if a > b:\n        return b\n    return a",
         "maximum", [((3, 5), 5), ((9, 2), 9)]),
    ]
    tasks, truth = [], []
    for code, name, cases in items:
        tasks.append(f"This Python function has a bug. Find it and provide the "
                     f"corrected code.\n```python\n{code}\n```")
        truth.append({"kind": "code", "fn": name, "cases": cases})
    return tasks, truth


def gen_logic():
    tasks, truth = [], []
    tasks.append("Alice, Bob and Carol ran a race. Alice finished before Bob. "
                 "Carol finished before Bob. Who finished last?")
    truth.append({"kind": "contains", "value": "bob"})
    tasks.append("Three boxes: red, green, blue. The red box is heavier than green. "
                 "Blue is lighter than green. Which box is the lightest?")
    truth.append({"kind": "contains", "value": "blue"})
    tasks.append("If all bloops are razzies and all razzies are lazzies, are all "
                 "bloops definitely lazzies? Answer yes or no.")
    truth.append({"kind": "contains", "value": "yes"})
    return tasks, truth


GENERATORS = {
    "factual": gen_factual, "math": gen_math, "sentiment": gen_sentiment,
    "summarization": gen_summary, "ner": gen_ner, "code_generation": gen_codegen,
    "code_debug": gen_debug, "logic": gen_logic,
}


def build():
    tasks, truth = [], {}
    i = 0
    for cat, gen in GENERATORS.items():
        ps, ts = gen()
        for p, t in zip(ps, ts):
            tid = f"{cat}_{i}"
            tasks.append({"task_id": tid, "prompt": p})
            t["category"] = cat
            truth[tid] = t
            i += 1
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(tasks, open(os.path.join(OUT_DIR, "tasks.json"), "w"), indent=2)
    json.dump(truth, open(os.path.join(OUT_DIR, "truth.json"), "w"), indent=2)
    print(f"wrote {len(tasks)} tasks to {OUT_DIR}/tasks.json")
    print(f"wrote ground truth to {OUT_DIR}/truth.json")


# --------------------------------------------------------------- judging
def run_code(code, fn, cases):
    src = f"{code}\n\nimport json,sys\n_r=[]\nfor _a in {cases!r}:\n"
    src += ("    _args=_a[0] if isinstance(_a[0],tuple) else (_a[0],)\n"
            "    try:\n"
            f"        _r.append(({fn}(*_args)==_a[1]))\n"
            "    except Exception:\n        _r.append(False)\n"
            "print(json.dumps(_r))\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        out = subprocess.run([sys.executable, path], capture_output=True,
                             text=True, timeout=8)
        res = json.loads((out.stdout or "[]").strip().splitlines()[-1])
        return all(res) and len(res) == len(cases)
    except Exception:
        return False
    finally:
        os.unlink(path)


def judge_one(ans, t):
    a = (ans or "").strip()
    if not a:
        return False
    k = t["kind"]
    if k == "contains":
        return t["value"].lower() in a.lower()
    if k == "number":
        return numbers_close(final_number(a), t["value"], rel=1e-2)
    if k == "label":
        m = re.search(r"\b(positive|negative|neutral)\b", a.lower())
        return bool(m) and m.group(1) == t["value"]
    if k in ("wordmax", "sentmax"):
        body = re.sub(r"(?i)^\s*summary\s*[:\-]\s*", "", a).strip()
        if not all(w in body.lower() for w in t.get("must", [])):
            return False
        if k == "wordmax":
            return len(body.split()) <= t["value"]
        return len([s for s in re.split(r"[.!?]+", body) if s.strip()]) <= t["value"]
    if k == "ner":
        obj = parse_json_lenient(a)
        if not isinstance(obj, dict):
            return False
        got = " ".join(str(v).lower() for v in obj.values())
        need = [x for lst in t["value"].values() for x in lst]
        return sum(x.lower() in got for x in need) >= max(1, len(need) - 1)
    if k == "code":
        return run_code(extract_code(a), t["fn"], t["cases"])
    return False


def judge(results_path):
    truth = json.load(open(os.path.join(OUT_DIR, "truth.json")))
    results = {r["task_id"]: r.get("answer", "")
               for r in json.load(open(results_path))}
    per = {}
    for tid, t in truth.items():
        ok = judge_one(results.get(tid, ""), t)
        c = t["category"]
        per.setdefault(c, [0, 0])
        per[c][0] += int(ok)
        per[c][1] += 1
    total_ok = sum(v[0] for v in per.values())
    total = sum(v[1] for v in per.values())
    print("=== JUDGE (proxy accuracy) ===")
    for c in GENERATORS:
        if c in per:
            ok, n = per[c]
            print(f"  {c:16s} {ok}/{n}  ({100*ok//max(1,n)}%)")
    print(f"  {'OVERALL':16s} {total_ok}/{total}  ({100*total_ok//max(1,total)}%)")
    print("\nRead output/stats.json for TOTAL_REMOTE_TOKENS + per-category routing.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", metavar="RESULTS_JSON")
    a = ap.parse_args()
    if a.judge:
        judge(a.judge)
    else:
        build()
