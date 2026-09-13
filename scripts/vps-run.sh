#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# vps-run.sh -- run one pipeline task on the server, from this laptop.
#
#     bash scripts/vps-run.sh status          (read-only: what is deployed)
#     bash scripts/vps-run.sh refresh         (the three live sources, then dbt)
#     bash scripts/vps-run.sh bank-of-canada
#     bash scripts/vps-run.sh statcan-cpi
#     bash scripts/vps-run.sh apciq
#     bash scripts/vps-run.sh dbt-build
#
# This is the same entry point n8n uses, reached the same way, so a task that
# works here works there. The difference is only the key: this script connects
# with the admin key, n8n with a restricted one that can run nothing else.
#
# The exit code is the server's own -- 0 success, 64 unknown task, 69 another
# run in progress, 70 a step failed -- so this can be chained in a shell.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

TASK="${1:-}"

# The same whitelist as the server, applied again here. Not belt-and-braces:
# $TASK is interpolated into a command string that a remote shell will parse,
# so without this a stray semicolon would be executed on the server with the
# admin key. Refusing by pattern beats quoting carefully.
case "$TASK" in
  refresh|bank-of-canada|statcan-cpi|apciq|dbt-build|status) ;;
  *)
    echo "Usage: bash scripts/vps-run.sh <task>" >&2
    echo "Tasks: refresh bank-of-canada statcan-cpi apciq dbt-build status" >&2
    exit 64
    ;;
esac

VPS_HOST="$(env_require VPS_HOST)"
[ -f "$SSH_KEY" ] || { echo "FAIL: ssh key not found at $SSH_KEY" >&2; exit 1; }

exec ssh -i "$SSH_KEY" -l "$VPS_USER" \
     -o BatchMode=yes -o ConnectTimeout=20 \
     "$VPS_HOST" "bash /opt/mhi/bin/vps-pipeline.sh $TASK"
