# ---------------------------------------------------------------------------
# lib.sh -- shared helpers. Not executable: other scripts source it.
# ---------------------------------------------------------------------------

# Repository root, whatever directory the caller is in.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# --- Reading .env ----------------------------------------------------------

# Read one key from .env without sourcing it. Sourcing executes the file, so a
# password containing a backtick or $ would be run as code instead of read as
# a value. This only ever reads.
env_get() {
  [ -f "$ENV_FILE" ] || return 1
  sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" \
    | tail -n1 \
    | sed 's/^"\(.*\)"$/\1/; s/^'\''\(.*\)'\''$/\1/'
}

# Same, but fails loudly when the key is absent or empty.
env_require() {
  local value
  value="$(env_get "$1")" || { echo "FAIL: .env not found at $ENV_FILE" >&2; return 1; }
  [ -n "$value" ] || { echo "FAIL: $1 is missing from .env" >&2; return 1; }
  printf '%s' "$value"
}

# A real environment variable always wins over .env, which is what lets a CI
# job or a one-off run point somewhere else without editing a tracked file.
env_or_default() {
  local name="$1" fallback="$2" value
  value="${!name:-}"
  [ -n "$value" ] || value="$(env_get "$name" 2>/dev/null || true)"
  printf '%s' "${value:-$fallback}"
}

# --- Where a client dials the database -------------------------------------
#
# Two supported layouts, and this is why the port is configurable:
#
#   database on a remote server : reached through the SSH tunnel, port 15432
#   database on this machine    : docker compose up -d, port 5432, no tunnel
#
# The scripts never ask "is the tunnel open". They ask "does the database
# answer", which is true in both layouts.
DB_HOST="$(env_or_default MHI_DB_HOST 127.0.0.1)"
DB_PORT="$(env_or_default MHI_DB_PORT 15432)"

# The tunnel binds the very port clients dial, so there is only one number.
TUNNEL_PORT="$DB_PORT"

# --- Server access ---------------------------------------------------------

# Both come from .env so the repository works on someone else machine without
# editing a script. The defaults match .env.example.
VPS_USER="$(env_or_default VPS_USER root)"
SSH_KEY="$(env_or_default VPS_SSH_KEY "$HOME/.ssh/id_ed25519_mhi_vps")"
# Expand a leading tilde ourselves. .env is not a shell script, so nothing
# expands it for us, and Git Bash on this machine drops the character on paste
# anyway -- which is exactly how it would end up wrong.
case "$SSH_KEY" in
  "~/"*) SSH_KEY="$HOME/${SSH_KEY#\~/}" ;;
esac

# --- The SSH tunnel --------------------------------------------------------

# Control socket: the tunnel own name tag. `ssh -O check|exit` acts on THIS
# connection and no other.
#
# Why not identify the tunnel by "whoever listens on the port": on Git Bash,
# `ssh -f` forks through the MSYS emulation layer, and Windows keeps attributing
# the socket to the PID that created it -- a PID that no longer exists. Measured
# on 2026-08-22: netstat said 15528, the live ssh.exe was 13732. A control
# socket removes the guesswork entirely.
TUNNEL_SOCKET="$HOME/.ssh/mhi-tunnel.sock"

# Is our tunnel alive? Asks the control socket, not the process table.
# ssh still wants a host argument even when the socket decides the connection,
# so we hand it the real one from .env.
tunnel_is_up() {
  local host
  [ -S "$TUNNEL_SOCKET" ] || return 1
  host="$(env_get VPS_HOST)" || return 1
  ssh -S "$TUNNEL_SOCKET" -O check -l "$VPS_USER" "$host" >/dev/null 2>&1
}

# --- Is the database actually there? ---------------------------------------

project_python() {
  local py="$REPO_ROOT/.venv/Scripts/python.exe"
  [ -x "$py" ] || py="$REPO_ROOT/.venv/bin/python"
  [ -x "$py" ] || py="python"
  printf '%s' "$py"
}

# Speaks the first message of the PostgreSQL protocol and checks the answer.
# An open port proves nothing; a reply proves a database.
db_is_reachable() {
  "$(project_python)" "$REPO_ROOT/scripts/check_tunnel.py" "$DB_HOST" "$DB_PORT" >/dev/null 2>&1
}

# Printed when it is not. Covers both layouts rather than assuming one.
db_unreachable_hint() {
  echo "FAIL: no database answers at $DB_HOST:$DB_PORT." >&2
  echo "      If it runs on a remote server : bash scripts/tunnel-start.sh" >&2
  echo "      If it runs on this machine    : docker compose up -d, and set" >&2
  echo "                                      MHI_DB_PORT=5432 in .env" >&2
}

# Informational only: which Windows PID currently listens on a local port.
# May be stale (see TUNNEL_SOCKET above) -- never use it to decide what to kill.
port_pid() {
  netstat -ano 2>/dev/null \
    | tr -d '\r' \
    | awk -v p=":$1" '$1 ~ /^TCP$/ && $2 ~ p"$" && $4 == "LISTENING" { print $5 }' \
    | head -n1
}
