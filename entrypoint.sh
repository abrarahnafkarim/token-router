#!/usr/bin/env bash
# Universal entrypoint for hackathon evaluation runners.
# Handles: direct invocation, shell-wrapped invocation, positional args.
# Does NOT use set -e — we want Python's own error handling to run.

# If the runner passes an explicit interpreter/shell command, exec it directly.
case "$1" in
    python|python3|/bin/sh|/bin/bash|sh|bash)
        exec "$@"
        ;;
esac

# Find the python binary available in this image.
if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo "FATAL: no python found" >&2
    exit 1
fi

exec "$PY" -m agent.main "$@"
