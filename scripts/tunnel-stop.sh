#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# tunnel-stop.sh -- close the SSH tunnel opened by tunnel-start.sh.
#
# Closes exactly the connection named by our control socket. No PID hunting,
# so it can never kill another SSH session by accident. The VPS is untouched.
#
# Usage:  bash scripts/tunnel-stop.sh
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if ! tunnel_is_up; then
  echo "No tunnel running. Nothing to close."
  rm -f "$TUNNEL_SOCKET"
  exit 0
fi

VPS_HOST="$(env_require VPS_HOST)"
ssh -S "$TUNNEL_SOCKET" -O exit -l "$VPS_USER" "$VPS_HOST"
rm -f "$TUNNEL_SOCKET"

# Verify rather than assume: the port must now refuse connections.
#
# "The check did not succeed" is NOT "the port is shut". Until 2026-09-15 this
# read any non-zero exit as shut, so a missing interpreter (127) or a crash
# passed as a verification -- and the port probed was always 15432, whatever
# MHI_DB_PORT said. Shut is proven only by the check's own words.
RC=0
OUT="$("$(project_python)" "$REPO_ROOT/scripts/check_tunnel.py" 127.0.0.1 "$TUNNEL_PORT" 2>&1)" || RC=$?
if [ "$RC" -eq 0 ]; then
  echo "FAIL: something still answers on 127.0.0.1:$TUNNEL_PORT" >&2
  exit 1
fi
if ! printf '%s' "$OUT" | grep -q "cannot reach"; then
  echo "FAIL: could not verify that 127.0.0.1:$TUNNEL_PORT is shut. The check said:" >&2
  printf '      %s\n' "$OUT" >&2
  exit 1
fi
echo "Tunnel closed and verified shut."
