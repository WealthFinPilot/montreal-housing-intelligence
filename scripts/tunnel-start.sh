#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# tunnel-start.sh -- open the SSH tunnel to the MHI database.
#
#   your laptop 127.0.0.1:15432  ->  ssh  ->  VPS 127.0.0.1:5432
#
# The database is published on the server's loopback only, so this tunnel is
# the ONLY way in. Nothing is exposed to the internet: the traffic travels
# inside the existing, encrypted SSH connection.
#
# Safe to run twice: if the tunnel is already up, it says so and exits 0.
#
# Usage:  bash scripts/tunnel-start.sh
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if tunnel_is_up; then
  echo "Tunnel already open on 127.0.0.1:$TUNNEL_PORT. Nothing to do."
  exit 0
fi

VPS_HOST="$(env_require VPS_HOST)"
REMOTE_PORT="$(env_get POSTGRES_PORT)"; REMOTE_PORT="${REMOTE_PORT:-5432}"
[ -f "$SSH_KEY" ] || { echo "FAIL: ssh key not found at $SSH_KEY" >&2; exit 1; }

# A socket file left over from a crashed session would block the new master.
rm -f "$TUNNEL_SOCKET"

echo "Opening tunnel 127.0.0.1:$TUNNEL_PORT -> VPS 127.0.0.1:$REMOTE_PORT ..."

# -f  : go to the background once authentication succeeded
# -N  : forward ports only, do not open a remote shell
# -M -S : become the master of a named control socket, so tunnel-stop.sh can
#         close THIS connection and nothing else
# -L  : the tunnel itself. The leading 127.0.0.1 keeps the local end private
#       to this machine -- without it, anyone on the same wifi could use it.
# -o ExitOnForwardFailure=yes : if the local port cannot be taken, fail instead
#       of leaving a connection that forwards nothing.
# -o BatchMode=yes            : never hang waiting for a password prompt.
# -o ServerAliveInterval=30   : detect a dead link instead of freezing.
ssh -f -N -M -S "$TUNNEL_SOCKET" \
    -L "127.0.0.1:$TUNNEL_PORT:127.0.0.1:$REMOTE_PORT" \
    -i "$SSH_KEY" -l root \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    "$VPS_HOST"

if ! tunnel_is_up; then
  echo "FAIL: ssh returned but the control socket reports no master connection" >&2
  exit 1
fi

# Open port is not the same as working database. Ask PostgreSQL itself.
python "$REPO_ROOT/scripts/check_tunnel.py"

echo "Tunnel OPEN. Close it with:  bash scripts/tunnel-stop.sh"
