#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# vps-pipeline.sh -- the ONLY thing n8n is allowed to run on the server.
#
# This script never runs on the laptop. It is installed at /opt/mhi/bin by
# scripts/deploy-vps.sh and named as a forced command in the authorized_keys
# entry of the dedicated n8n key:
#
#     command="/opt/mhi/bin/vps-pipeline.sh",no-port-forwarding,...  ssh-ed25519 AAAA...
#
# A forced command means SSH ignores whatever command the client asked for and
# runs this one instead, putting the client's request in SSH_ORIGINAL_COMMAND.
# That string is attacker-controlled input: it is matched against a whitelist
# below and NEVER evaluated, expanded, or passed to a shell.
#
#     bash scripts/vps-pipeline.sh refresh        (what n8n asks for weekly)
#     bash scripts/vps-pipeline.sh status         (read-only, no ingestion)
#
# Exit codes, because n8n cannot ask the database how it went. Measured on
# 2026-09-13: the n8n container sits on another Docker network and our database
# publishes on the server loopback only, so no Postgres node can reach it. The
# verdict therefore has to travel through the exit code and stdout.
#
#     0   everything succeeded
#    64   the requested task is not on the whitelist
#    69   another run holds the lock
#    70   an ingestion or dbt step failed  (details on stdout)
# ---------------------------------------------------------------------------
set -euo pipefail

# --- Where things live on the server ---------------------------------------
MHI_ROOT="${MHI_ROOT:-/opt/mhi}"
REPO_DIR="$MHI_ROOT/repo"
ENV_FILE="$MHI_ROOT/.env"
LOCK_FILE="$MHI_ROOT/var/pipeline.lock"

# The two writable directories, passed to Compose through the environment.
# Exported rather than written into .env: the shell environment wins over the
# env file in Compose, so nothing has to be added to a file full of secrets.
export MHI_DATA_DIR="$MHI_ROOT/var/data"
export MHI_ARTIFACTS_DIR="$MHI_ROOT/var/dbt"

# --- Which task was asked for ----------------------------------------------
#
# An argument when a human types it; SSH_ORIGINAL_COMMAND when the forced
# command intercepts n8n's request.
TASK="${1:-${SSH_ORIGINAL_COMMAND:-}}"

# n8n's SSH node has a mandatory "Working Directory" field, default "/", and
# the library underneath it (node-ssh) implements that field by rewriting the
# command:
#
#     if (options.cwd) { command = `cd ${shellEscape([options.cwd])} ; ${command}` }
#
# So a node asking for "refresh" actually sends "cd / ; refresh", and the
# whitelist below would refuse it -- with a message pointing at the task name
# rather than at the field that mangled it. Read in the node-ssh source on
# 2026-09-13 rather than discovered in production.
#
# The prefix is RECOGNISED AND DISCARDED, never executed: no cd happens, this
# is a pattern match on a string. What remains still has to be on the
# whitelist, so nothing is loosened -- "cd / ; rm -rf /" still fails on the
# whitelist exactly as before.
if [[ "$TASK" =~ ^cd[[:space:]]+(\'[^\']*\'|\"[^\"]*\"|[^\;[:space:]]+)[[:space:]]*\;[[:space:]]*(.*)$ ]]; then
  TASK="${BASH_REMATCH[2]}"
fi

# Trim surrounding whitespace, so a trailing newline from a text field does not
# turn "refresh" into something that matches nothing.
TASK="${TASK#"${TASK%%[![:space:]]*}"}"
TASK="${TASK%"${TASK##*[![:space:]]}"}"

# The whitelist. Anything not matching exactly is refused, unexecuted and
# unexpanded. This `case` is the entire security boundary of the SSH key: with
# it, a compromised or merely mistaken n8n workflow can ask for one of six
# things; without it, it would have a shell on this host.
case "$TASK" in
  refresh|bank-of-canada|statcan-cpi|apciq|dbt-build|status) ;;
  "")
    echo "REFUSED: no task given." >&2
    echo "Expected one of: refresh bank-of-canada statcan-cpi apciq dbt-build status" >&2
    exit 64
    ;;
  *)
    # The rejected string is printed quoted so a typo is diagnosable, and it is
    # never interpreted.
    printf 'REFUSED: %q is not an allowed task.\n' "$TASK" >&2
    echo "Expected one of: refresh bank-of-canada statcan-cpi apciq dbt-build status" >&2
    exit 64
    ;;
esac

# --- Sanity, before anything is started -------------------------------------
[ -d "$REPO_DIR" ] || { echo "FAIL: $REPO_DIR is missing. Deploy first." >&2; exit 70; }
[ -f "$ENV_FILE" ] || { echo "FAIL: $ENV_FILE is missing." >&2; exit 70; }

mkdir -p "$MHI_ROOT/var"

say() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# --- One run at a time ------------------------------------------------------
#
# n8n retries, a human debugging, and a schedule that fires while the previous
# run is still going are three ways to end up ingesting the same source twice
# at once. The loaders are idempotent, so the result would still be correct --
# but two dbt builds racing on the same schema is not something to find out
# about in production. Non-blocking on purpose: a second run should say so and
# leave, not queue up behind a build.
exec 9>"$LOCK_FILE"
if ! flock --nonblock 9; then
  say "REFUSED: another pipeline run is already in progress."
  exit 69
fi

# --- How a command is run ---------------------------------------------------
#
# --env-file points at the single .env on this server: there is no second copy
# of the credentials anywhere. -f fixes the compose file, and because Compose
# resolves relative paths against the directory of that file, the read-only
# bind mount of "." lands on $REPO_DIR.
compose() {
  docker compose --env-file "$ENV_FILE" -f "$REPO_DIR/docker-compose.yml" "$@"
}

# --rm so no stopped container is left behind after every schedule tick.
runner() {
  compose run --rm runner "$@"
}

FAILURES=()

step() {
  local label="$1"; shift
  say "START  $label"
  if runner "$@"; then
    say "OK     $label"
  else
    local code=$?
    say "FAILED $label (exit $code)"
    FAILURES+=("$label")
  fi
}

# --- The tasks --------------------------------------------------------------
#
# Only three sources are scheduled, and that is a measurement rather than an
# oversight. The other five -- the 2021 census, the geographic attribute file,
# the administrative boundaries, the neighbourhoods, the census tract
# boundaries -- are frozen: re-running them would re-download hundreds of
# megabytes to insert zero rows. They stay available as manual commands.
ingest_bank_of_canada() { step "bank of canada"  python -m ingestion.bank_of_canada.run; }
ingest_statcan_cpi()    { step "statcan cpi"     python -m ingestion.statcan.run --only statcan_consumer_price_index; }
ingest_apciq()          { step "apciq barometer" python -m ingestion.apciq.run; }

# One build after ALL ingestion, never one per source. Two reasons, and the
# second is the important one: a dbt build costs real CPU on a 2-vCPU box
# shared with a production n8n, and the models are cross-dependent -- the CPI
# restates APCIQ prices, so assert_every_priced_quarter_can_be_indexed can fail
# transiently if a new APCIQ quarter is built before the CPI that indexes it.
#
# --project-dir because the container's working directory is /app, the root of
# the repository, while the dbt project lives one level down in /app/dbt.
# --no-use-colors because this output ends up in an n8n execution log, where
# ANSI escapes are printed literally rather than rendered.
build_dbt() { step "dbt build" dbt --no-use-colors build --project-dir /app/dbt; }

case "$TASK" in
  refresh)
    say "TASK refresh -- the three sources that still publish, then dbt"
    ingest_bank_of_canada
    ingest_statcan_cpi
    ingest_apciq
    build_dbt
    ;;
  bank-of-canada) ingest_bank_of_canada; build_dbt ;;
  statcan-cpi)    ingest_statcan_cpi;    build_dbt ;;
  apciq)          ingest_apciq;          build_dbt ;;
  dbt-build)      build_dbt ;;
  status)
    say "TASK status -- read only, nothing is ingested"
    say "deployed commit: $(cat "$REPO_DIR/DEPLOYED_COMMIT" 2>/dev/null || echo unknown)"
    compose ps
    ;;
esac

# --- The verdict ------------------------------------------------------------
if [ "${#FAILURES[@]}" -gt 0 ]; then
  say "PIPELINE FAILED -- ${#FAILURES[@]} step(s): ${FAILURES[*]}"
  exit 70
fi

say "PIPELINE OK -- task $TASK"
