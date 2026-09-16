#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-n8n-key.sh -- give n8n a key that can do exactly one thing.
#
#     bash scripts/setup-n8n-key.sh            (in Git Bash)
#
# n8n runs in a container on the same server as the database, but it cannot
# reach either the code or the database: no Docker socket is mounted, and its
# network (root_default) is not the database's (mhi_default), which publishes
# on the server loopback only. Measured on 2026-09-13. So n8n asks the HOST to
# run the pipeline, over SSH, and this script creates the key it asks with.
#
# What makes that safe is not the key, it is the authorized_keys entry:
#
#   restrict          every forwarding off, no pty, no user rc file
#   command="..."     SSH runs THIS and ignores whatever the client asked for,
#                     putting the client's request in SSH_ORIGINAL_COMMAND,
#                     which vps-pipeline.sh matches against a whitelist and
#                     never evaluates
#   from="..."        the key is refused from anywhere but the Docker subnet.
#                     This host has no firewall (verified in J2) and sshd
#                     listens on 0.0.0.0:22, so a leaked key would otherwise be
#                     usable from the internet.
#
# The private key is written to this laptop and NEVER printed, committed, or
# sent anywhere. Pasting it into n8n is a manual step, done by a human, and the
# script says so at the end.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

VPS_HOST="$(env_require VPS_HOST)"
[ -f "$SSH_KEY" ] || { echo "FAIL: admin ssh key not found at $SSH_KEY" >&2; exit 1; }

N8N_KEY="$HOME/.ssh/id_ed25519_mhi_n8n"
FORCED_COMMAND="/opt/mhi/bin/vps-pipeline.sh"

# The Docker subnet n8n sits on, measured rather than assumed. Override if
# Docker ever renumbers the network: the symptom would be a plain
# "Permission denied (publickey)" from the n8n node.
N8N_FROM="${MHI_N8N_FROM:-172.18.0.0/16}"

ssh_do() {
  ssh -i "$SSH_KEY" -l "$VPS_USER" \
      -o BatchMode=yes -o ConnectTimeout=20 \
      "$VPS_HOST" "$1"
}

# --- 1. The key pair --------------------------------------------------------
#
# No passphrase: n8n has nobody to type one. That is precisely why the key is
# worth restricting -- its only protection is what authorized_keys allows it
# to do.
if [ -f "$N8N_KEY" ]; then
  echo "-- key already exists at $N8N_KEY, reusing it"
else
  echo "-- creating a dedicated key at $N8N_KEY"
  ssh-keygen -t ed25519 -N "" -C "mhi-n8n-pipeline" -f "$N8N_KEY" >/dev/null
fi

PUBLIC_KEY="$(cat "$N8N_KEY.pub")"
KEY_BODY="$(printf '%s' "$PUBLIC_KEY" | awk '{print $2}')"

# --- 2. Install it, restricted ----------------------------------------------
#
# Idempotent by key body: re-running replaces the entry instead of stacking a
# second, possibly less restricted, copy of the same key.
echo "-- installing the restricted entry on the server"
ssh_do "
  set -e
  mkdir -p \$HOME/.ssh && chmod 700 \$HOME/.ssh
  touch \$HOME/.ssh/authorized_keys && chmod 600 \$HOME/.ssh/authorized_keys

  # A dated backup before touching the file that decides who may log in.
  cp \$HOME/.ssh/authorized_keys \$HOME/.ssh/authorized_keys.bak.\$(date -u +%Y%m%dT%H%M%SZ)

  # Drop any previous entry for THIS key, matched on the key body so a changed
  # comment or option list cannot leave a stale line behind.
  grep -v '$KEY_BODY' \$HOME/.ssh/authorized_keys > \$HOME/.ssh/authorized_keys.new || true
  printf '%s\n' 'restrict,from=\"$N8N_FROM\",command=\"$FORCED_COMMAND\" $PUBLIC_KEY' >> \$HOME/.ssh/authorized_keys.new
  mv \$HOME/.ssh/authorized_keys.new \$HOME/.ssh/authorized_keys
  chmod 600 \$HOME/.ssh/authorized_keys
"

# --- 3. Positive controls ---------------------------------------------------
#
# An installed restriction that has never been tested is a belief. Both of
# these must behave as stated or the setup is not what it claims.
echo
echo "== Positive control 1: this key must NOT get a shell from here =="
# Two restrictions could stop this, and the message says which one did, because
# "it failed" is not a measurement.
OUT="$(ssh -i "$N8N_KEY" -l "$VPS_USER" -o BatchMode=yes -o ConnectTimeout=15 \
        "$VPS_HOST" "id" 2>&1 || true)"
if printf '%s' "$OUT" | grep -q "uid="; then
  echo "  FAIL  the key returned the output of \`id\`. It has a shell." >&2
  exit 1
fi
# From this laptop exactly one answer is a pass: refused before authentication.
# Anything else -- a timeout, a refused connection, an unknown host key -- means
# the server never judged the key at all, so "no shell" would be the absence of
# a measurement dressed as a pass. Until 2026-09-15 that case printed OK.
if printf '%s' "$OUT" | grep -qi "permission denied"; then
  echo "  OK    refused before authentication -- the from= clause bites."
  echo "        (This laptop is outside $N8N_FROM, which is the point: a leaked"
  echo "         key is unusable from the internet.)"
elif printf '%s' "$OUT" | grep -q "REFUSED: "; then
  echo "  FAIL  the key AUTHENTICATED from this laptop. command= held (the" >&2
  echo "        whitelist refused \`id\`), but from= did not: this laptop is not" >&2
  echo "        in $N8N_FROM, so a leaked key would work from the internet." >&2
  exit 1
else
  echo "  FAIL  the server never judged the key, so nothing was proven. It said:" >&2
  printf '        %s\n' "$OUT" | head -3 >&2
  exit 1
fi

echo
echo "== Positive control 2: the installed line really carries the restrictions =="
# The key body is never printed; only the option list in front of it, which is
# the part that does the work.
ssh_do "grep '$KEY_BODY' \$HOME/.ssh/authorized_keys | sed 's/ ssh-ed25519 .*//'" \
  | sed 's/^/        /'
echo "  Read the line above: it must start with restrict, then from=, then"
echo "  command=$FORCED_COMMAND"

echo
echo "== Positive control 3: the admin key still works =="
ssh_do 'echo "  OK    admin key answers"'

echo
cat <<'NOTE'
== What is left to do, by hand, in n8n ==

  1. Credentials > New > SSH, choose "Private Key".
     Host        172.18.0.1        (the Docker gateway; n8n reaches the host here)
     Port        22
     Username    root
     Private key paste the contents of the file below

  2. Print the private key yourself, in Git Bash, and paste it into n8n:

         cat ~/.ssh/id_ed25519_mhi_n8n

     It is deliberately not printed here, and it is not in the repository.

  3. The SSH node's command is ignored by the server: whatever it sends lands
     in SSH_ORIGINAL_COMMAND and is matched against the whitelist. Send the
     task name alone, e.g.   refresh
NOTE
