#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-venv.sh -- create the Python virtual environment and install the
# project dependencies at their exact pinned versions.
#
# Safe to run twice: an existing .venv is reused, not rebuilt.
#
# Usage:  bash scripts/setup-venv.sh
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$REPO_ROOT"

# Windows layout: the interpreter lives in .venv/Scripts, not .venv/bin.
VENV_PY=".venv/Scripts/python.exe"
[ -f "$VENV_PY" ] || VENV_PY=".venv/bin/python"

if [ ! -f "$VENV_PY" ]; then
  echo "Creating .venv ..."
  python -m venv .venv
  VENV_PY=".venv/Scripts/python.exe"
  [ -f "$VENV_PY" ] || VENV_PY=".venv/bin/python"
fi

echo "Interpreter: $("$VENV_PY" --version)"
"$VENV_PY" -m pip install --upgrade pip --quiet

# The lock file holds every package, direct and transitive, at the exact
# version this project was built and tested with.
echo "Installing from requirements.lock.txt ..."
"$VENV_PY" -m pip install -r requirements.lock.txt --quiet

echo
echo "Installed and verified:"
"$VENV_PY" -c "import psycopg, requests, pytest; print('  psycopg', psycopg.__version__); print('  requests', requests.__version__); print('  pytest', pytest.__version__)"
"$VENV_PY" -m pip show dbt-core dbt-postgres 2>/dev/null | grep -E '^(Name|Version):' | paste - - | sed 's/^/  /'
echo
echo "Done. Nothing else to activate: every project script calls $VENV_PY directly."
