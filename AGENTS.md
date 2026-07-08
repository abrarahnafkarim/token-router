# Standing rules for the coding agent (Google Antigravity)

0. Host is Ubuntu 24.04. Before Stage 1, ensure prerequisites exist:
   `build-essential`, `cmake`, and `docker buildx`. If `docker buildx version`
   fails, install `docker-buildx-plugin`. Never run `pip install` against the
   system Python (24.04 blocks it via PEP 668) — always use the Stage 4 venv,
   or `--break-system-packages` only if a venv is impossible. The Docker build
   (Stage 5+) needs none of this on the host.
1. Execute README.md stages strictly in order. Stop after each stage and
   wait for the user's review before continuing.
2. NEVER modify files under `agent/` unless the user explicitly asks.
   The agent code is the deliverable; your job is to build, test, and ship it.
3. NEVER print, commit, or copy `.env` contents. NEVER commit `models/`,
   `output/`, or any `.gguf` file (GitHub rejects files over 100 MB anyway).
4. Always build images with:
   `docker buildx build --platform linux/amd64 -t token-router:local --load .`
   Never build without the explicit platform flag.
5. After ANY change, run `python3 tests/dry_run.py` and report the result
   before proceeding.
6. Ask the user before any `docker push` or `git push`.
7. Docker runs that need Fireworks credentials must use `--env-file .env`
   (the shell does NOT export .env automatically).
