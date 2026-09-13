#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy-vps.sh -- put the committed code on the server and build the runner.
#
#     bash scripts/deploy-vps.sh            (in Git Bash)
#
# What travels, and why it cannot be anything else
# ------------------------------------------------
# The payload is `git archive HEAD`: the contents of the current COMMIT, piped
# straight into tar over SSH. That is a structural guarantee rather than a list
# of exclusions to keep up to date --
#
#   * .env is not tracked by git, so it CANNOT be sent. Neither can .venv/,
#     data/ (200 MB of APCIQ PDFs), or any secret a .gitignore rule covers.
#   * uncommitted work cannot be sent either, which is why this script refuses
#     to run with a dirty tree. Whatever executes on the server is a commit
#     you can name.
#
# The n8n production stack is never touched. The script ends by listing the
# containers, so the proof that root-n8n-1 and friends are still running is in
# the output rather than in a promise.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

VPS_HOST="$(env_require VPS_HOST)"
[ -f "$SSH_KEY" ] || { echo "FAIL: ssh key not found at $SSH_KEY" >&2; exit 1; }

MHI_ROOT="/opt/mhi"

ssh_do() {
  ssh -i "$SSH_KEY" -l "$VPS_USER" \
      -o BatchMode=yes -o ConnectTimeout=20 \
      "$VPS_HOST" "$1"
}

# --- 1. Refuse to deploy something that is not committed --------------------
cd "$REPO_ROOT"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "FAIL: the working tree has uncommitted changes to tracked files." >&2
  echo "      Deploying would put code on the server that no commit describes." >&2
  echo "      Commit (or stash) first, then deploy." >&2
  git status --short >&2
  exit 1
fi

# Untracked files are a warning, not a failure: they are simply not in the
# commit, so they will not be on the server. Said out loud because "I just
# wrote that file and the server does not have it" is otherwise a puzzling
# five minutes.
UNTRACKED="$(git ls-files --others --exclude-standard)"
if [ -n "$UNTRACKED" ]; then
  echo "NOTE: these files are untracked and will NOT be deployed:" >&2
  printf '      %s\n' $UNTRACKED >&2
fi

COMMIT="$(git rev-parse HEAD)"
COMMIT_SHORT="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "== Deploying $BRANCH @ $COMMIT_SHORT =="

# --- 2. Directory layout on the server --------------------------------------
#
# 10001 is the uid the runner image runs as (see Dockerfile). A name means
# nothing across the container boundary; the number is what matches.
echo "-- preparing $MHI_ROOT"
ssh_do "
  set -e
  mkdir -p $MHI_ROOT/bin $MHI_ROOT/var/data $MHI_ROOT/var/dbt
  chown -R 10001:10001 $MHI_ROOT/var/data $MHI_ROOT/var/dbt
  rm -rf $MHI_ROOT/repo.new
  mkdir -p $MHI_ROOT/repo.new
"

# --- 3. Ship the commit ------------------------------------------------------
echo "-- shipping the tree"
git archive --format=tar "$COMMIT" \
  | ssh -i "$SSH_KEY" -l "$VPS_USER" -o BatchMode=yes -o ConnectTimeout=20 \
        "$VPS_HOST" "tar -x -C $MHI_ROOT/repo.new"

# --- 4. Swap it in ----------------------------------------------------------
#
# Extract beside, then move: a deploy interrupted halfway leaves the previous
# code in place instead of a half-written tree.
echo "-- swapping in, stamping, installing the entry point"
ssh_do "
  set -e
  printf '%s\n' '$COMMIT' > $MHI_ROOT/repo.new/DEPLOYED_COMMIT
  printf 'branch %s\ndeployed_at %s\n' '$BRANCH' '$STAMP' >> $MHI_ROOT/repo.new/DEPLOYED_COMMIT
  rm -rf $MHI_ROOT/repo.old
  if [ -d $MHI_ROOT/repo ]; then mv $MHI_ROOT/repo $MHI_ROOT/repo.old; fi
  mv $MHI_ROOT/repo.new $MHI_ROOT/repo
  rm -rf $MHI_ROOT/repo.old

  # The forced command lives at a stable path outside the deployed tree, so
  # the authorized_keys entry never has to change and is readable on its own.
  install -m 0755 $MHI_ROOT/repo/scripts/vps-pipeline.sh $MHI_ROOT/bin/vps-pipeline.sh

  # Retire the standalone compose file left at $MHI_ROOT by J2.
  #
  # Measured on 2026-09-13: the first deploy RESTARTED mhi-postgres, which had
  # been up three weeks. Not because the definition changed -- diffing the two
  # files shows only additions, not one modified line of the postgres service --
  # but because Compose stamps each container with the project directory and
  # config file it came from. Invoking the same project from a different path
  # makes every existing container look out of sync, so Compose recreates it.
  # Harmless here, since the data lives in the named volume mhi_pgdata and was
  # verified intact afterwards, but it is a restart of the database on every
  # switch between the two files, forever.
  #
  # Renamed rather than deleted: reversible, and it makes the old path fail
  # with a plain \"no configuration file provided\" instead of silently working
  # and recreating containers. The file is not lost -- it is this repository.
  if [ -f $MHI_ROOT/docker-compose.yml ]; then
    mv $MHI_ROOT/docker-compose.yml $MHI_ROOT/docker-compose.yml.superseded
  fi
"

# --- 5. Build the runner image ----------------------------------------------
#
# Only rebuilds layers that changed. Since the Dockerfile copies nothing but
# requirements.lock.txt, a code-only deploy re-uses the cached dependency layer
# and finishes in seconds.
echo "-- building the runner image (first build downloads ~250 MB, later ones are cached)"
ssh_do "cd $MHI_ROOT && docker compose --env-file $MHI_ROOT/.env -f $MHI_ROOT/repo/docker-compose.yml build runner"

# --- 6. Prove the production stack is untouched ------------------------------
echo
echo "== Containers on the server =="
ssh_do 'docker ps --format "table {{.Names}}\t{{.Status}}"'

echo
echo "DEPLOYED $BRANCH @ $COMMIT_SHORT to $MHI_ROOT/repo"
echo "Next:  bash scripts/vps-run.sh status"
