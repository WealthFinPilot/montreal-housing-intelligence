# ---------------------------------------------------------------------------
# lib.sh -- shared helpers. Not executable: other scripts source it.
# ---------------------------------------------------------------------------

# Repository root, whatever directory the caller is in.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# Private key dedicated to this project. Revocable on its own, without touching
# the root password or the n8n stack.
# $HOME rather than ~ on purpose: Git Bash on this machine drops ~ on paste.
SSH_KEY="$HOME/.ssh/id_ed25519_mhi_vps"

# Local end of the SSH tunnel. Deliberately NOT 5432, so "15432" always means
# "the VPS, through the tunnel" and never "something local".
TUNNEL_PORT="${MHI_TUNNEL_PORT:-15432}"

# Control socket: the tunnel's own name tag. `ssh -O check|exit` acts on THIS
# connection and no other.
#
# Why not identify the tunnel by "whoever listens on port 15432": on Git Bash,
# `ssh -f` forks through the MSYS emulation layer, and Windows keeps attributing
# the socket to the PID that created it -- a PID that no longer exists. Measured
# on 2026-08-22: netstat said 15528, the live ssh.exe was 13732. A control
# socket removes the guesswork entirely.
TUNNEL_SOCKET="$HOME/.ssh/mhi-tunnel.sock"

# Read one key from .env without sourcing it. Sourcing executes the file, so a
# password containing a backtick or $ would be run as code instead of read as
# a value. This only ever reads.
env_get() {
  [ -f "$ENV_FILE" ] || { echo "FAIL: .env not found at $ENV_FILE" >&2; return 1; }
  sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" \
    | tail -n1 \
    | sed 's/^"\(.*\)"$/\1/; s/^'\''\(.*\)'\''$/\1/'
}

# Same, but fails loudly when the key is absent or empty.
env_require() {
  local value
  value="$(env_get "$1")" || return 1
  [ -n "$value" ] || { echo "FAIL: $1 is missing from .env" >&2; return 1; }
  printf '%s' "$value"
}

# Is our tunnel alive? Asks the control socket, not the process table.
# Returns 0 if the master connection is running.
# ssh still wants a host argument even when the socket decides the connection,
# so we hand it the real one from .env.
tunnel_is_up() {
  local host
  [ -S "$TUNNEL_SOCKET" ] || return 1
  host="$(env_get VPS_HOST)" || return 1
  ssh -S "$TUNNEL_SOCKET" -O check -l root "$host" >/dev/null 2>&1
}

# Informational only: which Windows PID currently listens on a local port.
# May be stale (see TUNNEL_SOCKET above) -- never use it to decide what to kill.
port_pid() {
  netstat -ano 2>/dev/null \
    | tr -d '\r' \
    | awk -v p=":$1" '$1 ~ /^TCP$/ && $2 ~ p"$" && $4 == "LISTENING" { print $5 }' \
    | head -n1
}
