"""Local GGUF model wrapper (llama-cpp-python).

Local tokens count as ZERO toward the leaderboard score — this is the entire
point of the hybrid architecture. Lazy import + graceful degradation: if the
model file is missing, the library is absent, loading fails, or measured
throughput is below MIN_TPS on the (unknown) scoring hardware, the agent
silently falls back to pure-Fireworks mode (Architecture B) instead of
crashing the run.

The warmup generation doubles as a throughput probe: measured tokens/sec
drives the router's adaptive placement (weak CPU -> hard categories remote).
"""
import os
import time


class LocalLM:
    def __init__(self, path, n_ctx=8192):
        self.ok = False
        self.err = None
        self.tps = 8.0    # decode tokens/sec (EMA, seeded by warmup)
        self.pp = 48.0    # prompt-processing tokens/sec (approximation)
        self.llm = None
        if not path or not os.path.exists(path):
            self.err = f"model file missing: {path}"
            return
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=path,
                n_ctx=n_ctx,
                n_threads=max(2, os.cpu_count() or 4),
                n_batch=256,
                seed=0,
                verbose=False,
            )
            self.ok = True
        except Exception as e:
            self.err = f"llama.cpp load failed: {e}"

    def _chat(self, user, max_tokens, temperature):
        out = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9 if temperature > 0 else 1.0,
        )
        usage = out.get("usage") or {}
        text = out["choices"][0]["message"].get("content") or ""
        return text, usage.get("completion_tokens")

    def warmup(self):
        """Tiny generation: pulls weights through the cache and measures real
        decode throughput so the router can adapt to unknown hardware."""
        if not self.ok:
            return
        try:
            t = time.monotonic()
            _, ct = self._chat("Reply with the single word: ready", 24, 0.0)
            dt = max(1e-3, time.monotonic() - t)
            self.tps = max(0.3, (ct or 4) / dt)
            self.pp = self.tps * 6.0
        except Exception as e:
            self.ok = False
            self.err = f"warmup failed: {e}"

    def gen(self, user, max_tokens, temperature=0.0):
        t = time.monotonic()
        text, ct = self._chat(user, max_tokens, temperature)
        dt = max(1e-3, time.monotonic() - t)
        if ct:
            self.tps = 0.7 * self.tps + 0.3 * (ct / dt)
        return text.strip()

    def estimate(self, prompt_tokens, gen_tokens):
        """Conservative wall-clock estimate for one generation (seconds)."""
        return (prompt_tokens / max(8.0, self.pp)
                + gen_tokens / max(0.3, self.tps) + 0.2)
