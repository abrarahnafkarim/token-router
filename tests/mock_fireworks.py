"""Minimal OpenAI-compatible mock server for exercising the REAL openai client
and the full main.py entrypoint end-to-end (no GGUF, no real credentials).

Returns category-appropriate answers and a realistic usage block so token
accounting is exercised. Used by tests/integration.sh.
"""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8919


def answer_for(user, json_mode):
    u = user.lower()
    if "is_prime" in u or ("python function" in u and "prime" in u):
        return "```python\ndef is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0:\n            return False\n    return True\n```"
    if "corrected code" in u or "find the bug" in u or "bug:" in u:
        return "Bug: divisor uses len(nums)-1 instead of len(nums)\n```python\ndef average(nums):\n    return sum(nums) / len(nums)\n```"
    if json_mode or "person" in u and "organization" in u:
        return '{"person":["Alice"],"organization":["Acme Corp"],"location":["Paris"],"date":["March 5, 2024"]}'
    if "sentiment" in u:
        return "Sentiment: positive\nReason: the reviewer praises the battery life and the screen."
    if "summar" in u or "one sentence" in u:
        return "Photosynthesis lets green plants turn sunlight, water, and carbon dioxide into glucose while releasing oxygen."
    if "discount" in u or "original price" in u:
        return "720 is 60% of the original, so original = 720 / 0.6.\nAnswer: 1200"
    if "finished last" in u or "who finished" in u:
        return "Both Alice and Carol finished before Bob.\nAnswer: Bob"
    if "capital" in u:
        return "The capital of Bangladesh is Dhaka."
    return "Answer: ok"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}")
        msgs = body.get("messages", [])
        user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
        json_mode = (body.get("response_format", {}) or {}).get("type") == "json_object"
        text = answer_for(user, json_mode)
        pt = max(1, len(user) // 4)
        ct = max(1, len(text) // 4)
        resp = {
            "id": "cmpl-mock", "object": "chat.completion", "model": body.get("model"),
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct,
                      "total_tokens": pt + ct},
        }
        out = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
