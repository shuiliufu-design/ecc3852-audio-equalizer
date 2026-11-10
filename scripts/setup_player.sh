#!/bin/sh
# Optional playback dependencies; uses the existing project environment.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
if [ ! -x .venv/bin/python ]; then
    sh scripts/setup.sh
fi
if command -v uv >/dev/null 2>&1; then
    uv --cache-dir .cache/uv pip install --python .venv/bin/python -r requirements-player.txt
else
    .venv/bin/python -m ensurepip --upgrade
    .venv/bin/python -m pip install --cache-dir .cache/pip -r requirements-player.txt
fi
.venv/bin/python -c 'import tkinter, sounddevice; print("Player ready; Tk", tkinter.TkVersion, "sounddevice", sounddevice.__version__)'
echo 'Run: .venv/bin/python play.py'
