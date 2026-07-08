"""Fireworks client. ALL remote calls go through FIREWORKS_BASE_URL (hard
competition rule — calls that bypass it are not recorded and invalidate the
run). Thread-safe token accounting via the API usage field so the local eval
harness reports exactly what the judging proxy will record.

Robustness: if the harness-provided base URL is a bare host (no /inference/v1
suffix), a failing first call falls through to `<base>/inference/v1`, then
`<base>/v1` — always the SAME host, never a different endpoint. Only
connection/404-class errors trigger the fallback; API errors raise so the
router can degrade instead of burning duplicate tokens.
"""
import os
import threading

_RETRIABLE = {"APIConnectionError", "APITimeoutError", "NotFoundError",
              "InternalServerError", "ConnectError"}


class Fireworks:
    def __init__(self):
        self.key = os.environ.get("FIREWORKS_API_KEY", "").strip()
        base = os.environ.get("FIREWORKS_BASE_URL", "").strip().rstrip("/")
        cands = [base]
        if base and not base.endswith("/v1"):
            cands += [base + "/inference/v1", base + "/v1"]
        self.bases = [b for b in dict.fromkeys(cands) if b]
        self.enabled = bool(self.key and base)
        self.timeout = float(os.environ.get("REMOTE_TIMEOUT", "25"))
        self._lock = threading.Lock()
        self._clients = {}
        self._base_i = 0
        self.calls = 0
        self.errors = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _client(self, base):
        with self._lock:
            if base not in self._clients:
                from openai import OpenAI
                self._clients[base] = OpenAI(
                    api_key=self.key, base_url=base,
                    timeout=self.timeout, max_retries=1)
            return self._clients[base]

    def chat(self, model, user, max_tokens=128, temperature=0.0,
             stop=None, json_mode=False, system=None):
        if not self.enabled:
            raise RuntimeError("Fireworks disabled: missing FIREWORKS_API_KEY / FIREWORKS_BASE_URL")
        msgs = ([{"role": "system", "content": system}] if system else [])
        msgs.append({"role": "user", "content": user})
        kw = dict(model=model, messages=msgs,
                  max_tokens=max_tokens, temperature=temperature)
        if stop:
            kw["stop"] = stop
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        last = None
        for i in range(self._base_i, len(self.bases)):
            try:
                r = self._client(self.bases[i]).chat.completions.create(**kw)
                u = getattr(r, "usage", None)
                with self._lock:
                    self._base_i = i
                    self.calls += 1
                    if u:
                        self.prompt_tokens += int(getattr(u, "prompt_tokens", 0) or 0)
                        self.completion_tokens += int(getattr(u, "completion_tokens", 0) or 0)
                return (r.choices[0].message.content or "").strip()
            except Exception as e:
                last = e
                with self._lock:
                    self.errors += 1
                if type(e).__name__ not in _RETRIABLE:
                    raise
        raise last if last else RuntimeError("all Fireworks base URLs failed")

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens
