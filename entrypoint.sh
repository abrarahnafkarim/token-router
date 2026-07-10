#!/usr/bin/env bash
set -e

# If the first argument is an explicit command executable (python, python3, /bin/sh, /bin/bash, sh, bash), execute it directly
if [ "$1" = "python" ] || [ "$1" = "python3" ] || [ "$1" = "/bin/sh" ] || [ "$1" = "/bin/bash" ] || [ "$1" = "sh" ] || [ "$1" = "bash" ]; then
    exec "$@"
fi

PY_CMD="python"
if ! command -v python >/dev/null 2>&1; then
    PY_CMD="python3"
fi

exec "$PY_CMD" -m agent.main "$@"
