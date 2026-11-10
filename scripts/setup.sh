#!/bin/sh
# Project-local setup; use a working Python without changing the system Python.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
if [ ! -x .venv/bin/python ]; then
    selected_python=""
    for candidate in python3.12 python3.13 python3.14 python3 "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"; do
        if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
            selected_python=$candidate
            break
        fi
    done
    if [ -z "$selected_python" ]; then
        echo 'Please install Python 3.12+ and rerun this script.' >&2
        exit 1
    fi
    "$selected_python" -m venv .venv
fi
if command -v uv >/dev/null 2>&1; then
    uv --cache-dir .cache/uv pip install --python .venv/bin/python -r requirements-lock.txt
else
    .venv/bin/python -m ensurepip --upgrade
    .venv/bin/python -m pip install --cache-dir .cache/pip -r requirements-lock.txt
fi
echo 'Environment ready. Run: .venv/bin/python run.py test'
