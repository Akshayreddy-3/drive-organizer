#!/bin/bash
# Drive Organizer — Mac launcher. Double-click to start the app.
# First run: creates a private Python environment in .venv and installs what the app needs.

cd "$(dirname "$0")" || exit 1

PY=""
for candidate in /usr/local/bin/python3 /opt/homebrew/bin/python3 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Drive Organizer needs Python 3.9 or newer."
  echo "Install it from https://www.python.org/downloads/ and double-click this file again."
  open "https://www.python.org/downloads/"
  read -r -p "Press Enter to close."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up (takes a few minutes)…"
  "$PY" -m venv .venv || { read -r -p "Setup failed. Press Enter to close."; exit 1; }
fi

# Install (or update) dependencies whenever requirements.txt changes
if ! cmp -s requirements.txt .venv/requirements-installed.txt; then
  echo "Installing what the app needs…"
  .venv/bin/python -m pip install --quiet --upgrade pip
  if .venv/bin/python -m pip install -r requirements.txt; then
    cp requirements.txt .venv/requirements-installed.txt
  else
    read -r -p "Install failed — check your internet connection. Press Enter to close."
    exit 1
  fi
fi

.venv/bin/python app.py
