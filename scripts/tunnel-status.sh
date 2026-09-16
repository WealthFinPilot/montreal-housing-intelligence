#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# tunnel-status.sh -- is the tunnel open, and is a real PostgreSQL behind it?
# Exit code 0 when both are true.
# Usage:  bash scripts/tunnel-status.sh
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if ! tunnel_is_up; then
  echo "Tunnel: CLOSED"
  exit 1
fi
echo "Tunnel: OPEN on 127.0.0.1:$TUNNEL_PORT"
"$(project_python)" "$REPO_ROOT/scripts/check_tunnel.py" 127.0.0.1 "$TUNNEL_PORT"
