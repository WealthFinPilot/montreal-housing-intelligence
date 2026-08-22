#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# check-vps.sh -- read-only status check of the MHI database on the VPS.
#
# Reads VPS_HOST from .env and never prints it. Every command it runs on the
# server is a read: nothing is started, stopped or modified. The n8n production
# stack (root-n8n-1, root-n8n-worker-1, n8n-postgres, redis, root-traefik-1) is
# only ever listed, never touched.
#
# Usage:  bash scripts/check-vps.sh
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

VPS_HOST="$(env_require VPS_HOST)"
[ -f "$SSH_KEY" ] || { echo "FAIL: ssh key not found at $SSH_KEY" >&2; exit 1; }

# -l root instead of root@host: Git Bash on this machine eats @ on paste.
SSH="ssh -i $SSH_KEY -l root -o BatchMode=yes -o ConnectTimeout=15 $VPS_HOST"

echo "== 1. SSH reachability =="
$SSH 'echo "SSH OK -- host $(hostname), uptime$(uptime -p | sed s/up//)"'

echo
echo "== 2. Containers currently running =="
$SSH 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

echo
echo "== 3. mhi-postgres detail =="
$SSH 'docker inspect -f "name={{.Name}} state={{.State.Status}} health={{.State.Health.Status}} restarts={{.RestartCount}}" mhi-postgres'

echo
echo "== 4. Tables and row counts in the raw layer =="
# No literal quotes inside the SQL on purpose: this string travels through
# bash -> ssh -> docker exec -> bash -> psql, and every layer strips one level
# of quoting. Ordering by schema instead of filtering on it avoids the problem.
$SSH 'docker exec mhi-postgres bash -lc "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY 1, 2\""'

echo
echo "ALL CHECKS DONE -- nothing was modified on the server."
