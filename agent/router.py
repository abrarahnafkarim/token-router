"""The cascade: classify -> local generate -> verify (AGREEMENT for MATH and
LOGIC) -> escalate once to Fireworks on verified failure.

Evaluation fixes baked in:
  #1/#2  MATH and LOGIC are trusted locally only when two independent local
         samples (t=0.0 and t=0.7) agree on the final answer — a wrong
         problem setup can fool an arithmetic recheck, but rarely reproduces
         itself under sampling noise. Disagreement -> escalate.
  #4     Category-conditional escalation: hard categories -> strongest
         allowed model; language categories -> the Gemma pick (sub-prize
         eligibility without betting the accuracy gate on it).

Remote escalations run on a small thread pool so their network latency
overlaps local CPU compute. As the deadline approaches, the router degrades
gracefully: local work is skipped when unaffordable, and every task always
receives some answer before results.json is written.
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from . import prompts
from . import verifiers as V
from .classifier import Cat, classify

BASE_PLAN = {
    Cat.FACTUAL:   dict(agree=False, lmax=120, rmax=110, hard=False),
    Cat.MATH:      dict(agree=True,  lmax=230, rmax=190, hard=True),
    Cat.SENTIMENT: dict(agree=False, lmax=48,  rmax=48,  hard=False),
    Cat.SUMMARY:   dict(agree=False, lmax=150, rmax=150, hard=False),
    Cat.NER:       dict(agree=False, lmax=150, rmax=150, hard=False, json=True),
    Cat.DEBUG:     dict(agree=False, lmax=360, rmax=340, hard=True),
    Cat.CODEGEN:   dict(agree=False, lmax=330, rmax=310, hard=True),
    Cat.LOGIC:     dict(agree=True,  lmax=230, rmax=210, hard=True),
}


class Router:
    def __init__(self, cfg, local, fw, sel, deadline):
        self.cfg = cfg
        self.local = local
        self.fw = fw
        self.sel = sel or {}
        self.dl = deadline
        self.pool = (ThreadPoolExecutor(max_workers=cfg.remote_workers)
                     if fw and fw.enabled else None)
        self.stats = []

    # ------------------------------------------------------------ public
    def solve_all(self, tasks):
        out, futs = {}, {}
        n = len(tasks)
        for i, t in enumerate(tasks):
            tid = str(t.get("task_id", i))
            prompt = str(t.get("prompt", "") or "")
            tasks_left = n - i
            cat = classify(prompt)
            plan = dict(BASE_PLAN[cat])
            lmax = prompts.max_tokens_for(cat, prompt, plan["lmax"])
            rmax = prompts.max_tokens_for(cat, prompt, plan["rmax"])

            ans, path = None, "local"
            if self._local_eligible(cat, prompt, plan, tasks_left, lmax):
                ans = self._try_local(cat, prompt, plan, lmax)
            if ans is None:
                if self.pool and self.dl.hard_remaining() > 6:
                    futs[tid] = (self.pool.submit(self._remote, cat, prompt, plan, rmax),
                                 cat, prompt)
                    path = "remote"
                else:
                    ans = self._last_resort(cat, prompt)
                    path = "fallback"
            if ans is not None:
                out[tid] = ans
            self.stats.append(dict(task_id=tid, category=cat.value, path=path))

        for tid, (f, cat, prompt) in futs.items():
            try:
                out[tid] = f.result(timeout=max(3.0, self.dl.hard_remaining() - 2))
            except Exception:
                f.cancel()
                out[tid] = self._last_resort(cat, prompt)
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)
        return out

    # ------------------------------------------------------------ local
    def _local_eligible(self, cat, prompt, plan, tasks_left, lmax):
        if not self.local or self.cfg.force_remote:
            return False

        # ── Three-tier DistilBERT routing (zero tokens) ──
        # "easy"      → proceed to local model confidently
        # "uncertain" → try local but force agreement verification
        # "hard"      → skip local entirely, escalate to remote
        try:
            from .infer_router import predict
            tier = predict(prompt)
            if tier == "hard":
                return False          # straight to remote
            if tier == "uncertain":
                plan["agree"] = True  # force double-check even for easy cats
        except Exception:
            pass  # DistilBERT missing/broken → fall through to heuristics

        if cat.value in self.cfg.remote_cats:
            return False
        ptoks = len(prompt) // 3  # conservative chars→tokens estimate
        if ptoks > self.cfg.local_ctx - lmax - 64:
            return False          # too long for local context: go remote
        mult = 2 if plan["agree"] else 1
        est = self.local.estimate(ptoks, lmax) * mult
        return self.dl.affordable(est, tasks_left)

    def _try_local(self, cat, prompt, plan, lmax):
        u = prompts.build(cat, prompt)
        try:
            a1 = self.local.gen(u, lmax, 0.0)
        except Exception:
            return None
        if plan["agree"]:
            try:
                a2 = self.local.gen(u, lmax, 0.7)
            except Exception:
                return None
            if not V.agree(cat, a1, a2):
                return None       # samples disagree -> don't trust -> escalate
        ok, fixed = V.verify(cat, a1, prompt)
        if ok:
            return fixed
        # One corrective local retry for summaries that broke their limit.
        if cat == Cat.SUMMARY:
            kind, nlim = V.parse_summary_constraint(prompt)
            if kind:
                lim = f"use at most {nlim} {kind}" if nlim else "use bullet points"
                retry = f"{u}\n\nYour previous answer broke the limit. Strictly {lim}."
                try:
                    a3 = self.local.gen(retry, lmax, 0.0)
                    ok3, f3 = V.verify(cat, a3, prompt)
                    if ok3:
                        return f3
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------ remote
    def _pick_model(self, cat):
        mapping = {
            Cat.SENTIMENT: "accounts/fireworks/models/gemma-4-26b-a4b-it",
            Cat.NER: "accounts/fireworks/models/gemma-4-26b-a4b-it",
            Cat.FACTUAL: "accounts/fireworks/models/gemma-4-26b-a4b-it",
            Cat.SUMMARY: "accounts/fireworks/models/gemma-4-26b-a4b-it",
            Cat.MATH: "accounts/fireworks/models/kimi-k2p7-code",
            Cat.LOGIC: "accounts/fireworks/models/kimi-k2p7-code",
            Cat.CODEGEN: "accounts/fireworks/models/minimax-m3",
            Cat.DEBUG: "accounts/fireworks/models/kimi-k2p7-code",
        }
        return mapping.get(cat)

    def _remote(self, cat, prompt, plan, rmax):
        model = self._pick_model(cat)
        if not model or not (self.fw and self.fw.enabled):
            return self._last_resort(cat, prompt)
        allowed = set(self.sel.get("all") or [])
        if allowed and model not in allowed:   # hard compliance guard
            # If the specific model is banned, fall back to whatever strong/language is allowed
            fallback = self.sel.get("strong") if plan.get("hard") else self.sel.get("language")
            model = fallback or allowed.pop() if allowed else None
            if not model:
                return self._last_resort(cat, prompt)
        u = prompts.build(cat, prompt)
        json_mode = bool(plan.get("json")) and not V.prompt_wants_custom_format(prompt)
        try:
            txt = self.fw.chat(model, u, max_tokens=rmax, json_mode=json_mode)
        except Exception:
            return self._last_resort(cat, prompt)
        ok, fixed = V.verify(cat, txt, prompt)
        if ok:
            return fixed

        # If verification failed (e.g. format broken), do one corrective remote retry if time allows.
        if not ok and self.dl.hard_remaining() > 8:
            try:
                retry_p = f"{u}\n\nYour previous answer was incorrectly formatted or invalid. Please follow the instructions exactly."
                txt2 = self.fw.chat(model, retry_p, max_tokens=rmax, json_mode=json_mode)
                ok2, f2 = V.verify(cat, txt2, prompt)
                if ok2:
                    return f2
            except Exception:
                pass

        return txt.strip() or self._last_resort(cat, prompt)

    # ------------------------------------------------------------ fallback
    def _last_resort(self, cat, prompt):
        """Never leave an answer empty while any capacity remains."""
        if self.local and getattr(self.local, "ok", False):
            gen_toks = min(96, BASE_PLAN[cat]["lmax"])
            est = self.local.estimate(len(prompt) // 3, gen_toks)
            if self.dl.hard_remaining() > est + 2:
                try:
                    return self.local.gen(prompts.build(cat, prompt), gen_toks, 0.0)
                except Exception:
                    pass
        return ""
