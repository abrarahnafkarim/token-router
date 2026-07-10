"""Entrypoint. Contract with the harness:
  read  /input/tasks.json   [{"task_id","prompt"}, ...]
  write /output/results.json [{"task_id","answer"}, ...]   (valid JSON, always)
  exit 0

Env injected by the harness at runtime (never hardcoded, never bundled):
  FIREWORKS_API_KEY, FIREWORKS_BASE_URL, ALLOWED_MODELS

Adaptive placement (measured at warmup on the unknown scoring hardware):
  local tps <  MIN_TPS  -> local disabled entirely (pure Fireworks, Arch B)
  local tps <  WEAK_TPS -> hard categories (math/logic/code) forced remote
  FORCE_REMOTE=1        -> Architecture B regardless
"""
import json
import os
import sys
import traceback

from .config import Cfg
from .deadline import Deadline
from .fireworks_client import Fireworks
from .local_model import LocalLM
from .model_select import choose, parse_allowed
from .router import Router


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_tasks(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("tasks") or data.get("data") or []
    tasks = []
    for i, t in enumerate(data):
        if not isinstance(t, dict):
            continue
        tid = t.get("task_id", t.get("id", i))
        tasks.append({"task_id": str(tid),
                      "prompt": str(t.get("prompt") or t.get("task") or "")})
    return tasks


def write_results(path, tasks, answers):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    seen, out = set(), []
    for t in tasks:
        tid = t["task_id"]
        if tid in seen:
            continue
        seen.add(tid)
        out.append({"task_id": tid, "answer": str(answers.get(tid, "") or "")})
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, path)  # atomic: never leaves a half-written file


def main():
    cfg = Cfg()
    dl = Deadline(cfg.time_limit, cfg.reserve)
    tasks = []
    try:
        tasks = load_tasks(cfg.input)
        log(f"[agent] {len(tasks)} tasks loaded")

        fw = Fireworks()
        allowed = parse_allowed(os.environ.get("ALLOWED_MODELS", ""))
        sel = choose(allowed)
        log(f"[agent] fw_enabled={fw.enabled} allowed={len(allowed)} "
            f"strong={sel.get('strong')} language={sel.get('language')}")

        if cfg.simple:
            from .simple import run_simple
            log("[agent] SIMPLE_MODE: accuracy-first clean passthrough")
            answers = run_simple(tasks, fw, sel, dl)
            log(f"[agent] model used: {getattr(run_simple, 'chosen_model', None)}")
            write_results(cfg.output, tasks, answers)
            filled = sum(1 for v in answers.values() if v)
            log(f"[agent] done in {dl.elapsed():.1f}s | answered={filled}/{len(tasks)} "
                f"remote calls={fw.calls} TOTAL_REMOTE_TOKENS={fw.total_tokens} "
                f"errors={fw.errors}")
            sys.exit(0)

        local = None
        if not cfg.force_remote and not cfg.local_disabled:
            try:
                lm = LocalLM(cfg.model_path, cfg.local_ctx)
                if lm.ok:
                    lm.warmup()
                if lm.ok and lm.tps >= cfg.min_tps:
                    local = lm
                    if lm.tps < cfg.weak_tps:
                        cfg.remote_cats |= {"math", "logic", "code_debug", "code_generation"}
                        log(f"[agent] weak local ({lm.tps:.1f} tps): hard categories -> remote")
                    else:
                        log(f"[agent] local ready ({lm.tps:.1f} tps)")
                else:
                    log(f"[agent] local unavailable ({lm.err or f'slow: {lm.tps:.1f} tps'}) "
                        f"-> pure Fireworks mode")
            except Exception as e:
                log(f"[agent] local unavailable (error: {e}) -> pure Fireworks mode")
                local = None

        router = Router(cfg, local, fw, sel, dl)
        answers = router.solve_all(tasks)
        write_results(cfg.output, tasks, answers)

        log(f"[agent] done in {dl.elapsed():.1f}s | remote calls={fw.calls} "
            f"prompt_toks={fw.prompt_tokens} completion_toks={fw.completion_tokens} "
            f"TOTAL_REMOTE_TOKENS={fw.total_tokens}")
        if cfg.debug:
            try:
                stats_path = os.path.join(os.path.dirname(cfg.output) or ".", "stats.json")
                with open(stats_path, "w", encoding="utf-8") as f:
                    json.dump(dict(
                        stats=router.stats,
                        prompt_tokens=fw.prompt_tokens,
                        completion_tokens=fw.completion_tokens,
                        total_remote_tokens=fw.total_tokens,
                        remote_calls=fw.calls,
                        remote_errors=fw.errors,
                        elapsed_s=round(dl.elapsed(), 1),
                        local_tps=(round(local.tps, 2) if local else None),
                    ), f)
            except Exception:
                pass
        sys.exit(0)

    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(file=sys.stderr)
        # Whatever happened, ship a valid results.json so the run is scoreable.
        try:
            write_results(cfg.output, tasks, {})
            sys.exit(0)
        except Exception:
            sys.exit(1)


if __name__ == "__main__":
    main()
