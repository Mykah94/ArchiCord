#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -u webui.py "$@"
fi
exec python3 -u webui.py "$@"
