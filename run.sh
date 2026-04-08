#!/bin/sh
# Always use the project venv (Arch / PEP 668: do not pip install system-wide).
cd "$(dirname "$0")" || exit 1
if ! test -x .venv/bin/python; then
  echo "No .venv found. Run once:" >&2
  echo "  cd \"$(pwd)\" && python -m venv .venv && .venv/bin/pip install -r requirements.txt PySide6" >&2
  exit 1
fi
exec .venv/bin/python computer_melter.py "$@"
