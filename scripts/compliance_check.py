#!/usr/bin/env python3
"""Pre-submission compliance scan. Catches the instant-disqualifier mistakes
before you push. Run: python3 scripts/compliance_check.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems, warnings = [], []


def rel(p):
    return os.path.relpath(p, ROOT)


# 1) No hardcoded Fireworks keys anywhere in shipped code.
key_re = re.compile(r"fw[_-]?[A-Za-z0-9]{20,}")
for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "models", "output", "__pycache__", ".venv")]
    for fn in files:
        if fn.endswith((".py", ".sh", ".md", ".txt", ".json")) and fn != ".env":
            p = os.path.join(dirpath, fn)
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if key_re.search(txt) and "fw_your" not in txt and "fw_xxx" not in txt:
                problems.append(f"possible hardcoded API key in {rel(p)}")

# 2) .env must be git-ignored and never referenced by the Dockerfile.
gi = os.path.join(ROOT, ".gitignore")
if not (os.path.exists(gi) and ".env" in open(gi).read()):
    problems.append(".env is not in .gitignore")
df = os.path.join(ROOT, "Dockerfile")
if os.path.exists(df):
    d = open(df).read()
    if re.search(r"COPY\s+\.env", d) or ".env" in re.findall(r"COPY\s+(.+)", d).__str__():
        problems.append("Dockerfile appears to COPY .env into the image")
    if "--platform" in d and "FROM" in d and re.search(r"FROM\s+--platform", d):
        warnings.append("Dockerfile hardcodes --platform in FROM; prefer the buildx flag")
    if "GGML_NATIVE=OFF" not in d:
        problems.append("Dockerfile missing GGML_NATIVE=OFF (portable CPU build) -> "
                        "risk of illegal-instruction crash on the scoring host")

# 3) models/ must be git-ignored (the 2.5GB GGUF must not enter git history).
if not (os.path.exists(gi) and re.search(r"(?m)^models/", open(gi).read())):
    problems.append("models/ is not git-ignored (GGUF will break the git push)")

# 4) Env vars must be read from os.environ, never assigned literals in code.
for mod in ("fireworks_client.py", "main.py", "config.py"):
    p = os.path.join(ROOT, "agent", mod)
    if os.path.exists(p):
        t = open(p).read()
        if re.search(r"FIREWORKS_API_KEY\s*=\s*['\"]", t):
            problems.append(f"{mod} assigns FIREWORKS_API_KEY a literal")

# 5) Reasoning-model ban present.
ms = os.path.join(ROOT, "agent", "model_select.py")
if os.path.exists(ms):
    t = open(ms).read()
    for tok in ("think", "r1", "qwq"):
        if tok not in t.lower():
            warnings.append(f"model_select may not ban '{tok}' reasoning models")

print("=== COMPLIANCE CHECK ===")
for w in warnings:
    print(f"  WARN  {w}")
if problems:
    for p in problems:
        print(f"  FAIL  {p}")
    print(f"\n{len(problems)} blocking issue(s). Fix before submitting.")
    sys.exit(1)
print("  OK    no blocking compliance issues")
print("\nManual checks still required:")
print("  - image built with: docker buildx build --platform linux/amd64")
print("  - GHCR/Docker Hub package set to PUBLIC")
print("  - compressed image size <= 10GB (docker images shows uncompressed; "
      "registry compresses ~2-3x)")
sys.exit(0)
