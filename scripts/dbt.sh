#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# dbt.sh -- run dbt with the project environment loaded.
#
#     bash scripts/dbt.sh debug
#     bash scripts/dbt.sh run
#     bash scripts/dbt.sh test
#     bash scripts/dbt.sh source freshness
#
# What it does before calling dbt:
#   1. checks the SSH tunnel is open, and says how to open it if not
#   2. reads the credentials from .env into the environment, never printing them
#   3. points dbt at dbt/profiles.yml, which contains no secret of its own
#
# Running dbt directly, outside this wrapper, fails on a missing environment
# variable. That is deliberate: it means a credential can never be silently
# picked up from somewhere unexpected.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if ! tunnel_is_up; then
  echo "FAIL: the SSH tunnel is closed, so the database is unreachable." >&2
  echo "      Open it with:  bash scripts/tunnel-start.sh" >&2
  exit 1
fi

export POSTGRES_DB="$(env_require POSTGRES_DB)"
export POSTGRES_USER="$(env_require POSTGRES_USER)"
export POSTGRES_PASSWORD="$(env_require POSTGRES_PASSWORD)"
export MHI_DB_HOST="${MHI_DB_HOST:-127.0.0.1}"
export MHI_DB_PORT="${MHI_DB_PORT:-$TUNNEL_PORT}"
export DBT_PROFILES_DIR="$REPO_ROOT/dbt"

DBT_BIN="$REPO_ROOT/.venv/Scripts/dbt.exe"
[ -x "$DBT_BIN" ] || DBT_BIN="$REPO_ROOT/.venv/bin/dbt"
[ -x "$DBT_BIN" ] || { echo "FAIL: dbt not found. Run: bash scripts/setup-venv.sh" >&2; exit 1; }

cd "$REPO_ROOT/dbt"
exec "$DBT_BIN" "$@"
