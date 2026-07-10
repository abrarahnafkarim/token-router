"""Runtime configuration. Everything tunable is an env var so day-of tuning
is a one-line Dockerfile ENV change (the harness only injects FIREWORKS_*
and ALLOWED_MODELS; all other vars keep their image defaults)."""
import os


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Cfg:
    def __init__(self):
        # Architecture B switch: skip local model entirely, pure Fireworks token-golf.
        self.force_remote = _flag("FORCE_REMOTE")
        self.local_disabled = _flag("LOCAL_DISABLED")
        # Accuracy-first mode: clean passthrough to the strongest model.
        self.simple = _flag("SIMPLE_MODE")
        self.model_path = os.environ.get("LOCAL_MODEL_PATH", "/app/models/local.gguf")
        self.local_ctx = int(os.environ.get("LOCAL_CTX", "2048"))
        # Time budget: finish comfortably inside the 10-minute hard cap.
        self.time_limit = int(os.environ.get("TIME_LIMIT", "575"))
        self.reserve = int(os.environ.get("TIME_RESERVE", "30"))
        self.remote_workers = int(os.environ.get("REMOTE_WORKERS", "6"))
        # Local throughput gates (tokens/sec), measured at warmup:
        #  below MIN_TPS  -> local disabled entirely (Architecture B)
        #  below WEAK_TPS -> hard categories forced remote
        self.min_tps = float(os.environ.get("MIN_TPS", "1.5"))
        self.weak_tps = float(os.environ.get("WEAK_TPS", "4"))
        # Comma-separated category names always routed remote,
        # e.g. REMOTE_CATS=math,logic  (values: factual, math, sentiment,
        # summarization, ner, code_debug, code_generation, logic)
        self.remote_cats = set(
            c.strip() for c in os.environ.get("REMOTE_CATS", "").lower().split(",") if c.strip()
        )
        self.debug = _flag("DEBUG")

        import sys
        args = [
            a for a in sys.argv[1:]
            if a not in ("python", "python3", "/bin/sh", "/bin/bash", "sh", "bash", "-m", "agent.main", "main.py")
            and not a.startswith("-c")
        ]
        in_path, out_path = None, None
        i = 0
        while i < len(args):
            if args[i] in ("-i", "--input", "--input-path") and i + 1 < len(args):
                in_path = args[i + 1]
                i += 2
            elif args[i] in ("-o", "--output", "--output-path") and i + 1 < len(args):
                out_path = args[i + 1]
                i += 2
            elif not args[i].startswith("-"):
                if not in_path:
                    in_path = args[i]
                elif not out_path:
                    out_path = args[i]
                i += 1
            else:
                i += 1

        self.input = in_path or os.environ.get("INPUT_PATH", "/input/tasks.json")
        self.output = out_path or os.environ.get("OUTPUT_PATH", "/output/results.json")
