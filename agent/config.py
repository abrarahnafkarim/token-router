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
        self.local_ctx = int(os.environ.get("LOCAL_CTX", "8192"))
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
        self.input = os.environ.get("INPUT_PATH", "/input/tasks.json")
        self.output = os.environ.get("OUTPUT_PATH", "/output/results.json")
