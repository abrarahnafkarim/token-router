"""Accuracy-first mode (SIMPLE_MODE=1).

One clean Fireworks call per task to the strongest allowed model, generous
max_tokens, high concurrency, and the model's RAW answer shipped verbatim.

No classifier, no local model, no verifiers, no prompt augmentation, no
normalization -- nothing that can truncate, reformat, or block a correct
answer. Its only job is to reveal whether the models can clear the accuracy
gate at all. Optimize tokens ONLY after this passes.

Two things that were silently costing accuracy and are fixed here:
  1. Empty answers from API errors/timeouts (scored as wrong) -> every empty
     answer is retried once.
  2. Correct answers mangled by our own post-processing / low token caps ->
     eliminated: the prompt goes through untouched and the reply ships raw.
"""
import os
from concurrent.futures import ThreadPoolExecutor


def run_simple(tasks, fw, sel, deadline):
    allowed = set(sel.get("all") or [])
    forced = os.environ.get("SIMPLE_FORCE_MODEL", "").strip()
    if forced and (not allowed or forced in allowed):
        model = forced
    else:
        model = sel.get("strong") or (sel.get("all") or [None])[0]
    max_toks = int(os.environ.get("SIMPLE_MAX_TOKENS", "1024"))
    workers = int(os.environ.get("SIMPLE_WORKERS", "16"))

    ids = [str(t.get("task_id", i)) for i, t in enumerate(tasks)]
    prompts = {ids[i]: str(t.get("prompt", "") or "") for i, t in enumerate(tasks)}
    answers = {tid: "" for tid in ids}

    run_simple.chosen_model = model  # for accurate logging by the caller
    if not (fw and fw.enabled) or not model or (allowed and model not in allowed):
        return answers  # nothing we can do; valid (empty) JSON still ships

    def one(tid):
        try:
            txt = fw.chat(model, prompts[tid], max_tokens=max_toks, temperature=0.0)
            return tid, (txt or "").strip()
        except Exception as e:
            print("SIMPLE ERROR:", type(e).__name__, e)
            return tid, ""

    todo = list(ids)
    for _ in range(2):  # initial pass + one retry for any empties
        if not todo or deadline.hard_remaining() < 8:
            break
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for tid, ans in pool.map(one, todo):
                if ans:
                    answers[tid] = ans
        todo = [tid for tid in ids if not answers[tid]]
    return answers
