#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# migrate.sh -- bring a running database up to date with sql/bootstrap/.
#
#     bash scripts/migrate.sh
#
# Docker executes sql/bootstrap/ once, when it creates the volume. This script
# executes the same files against a database that already exists, skipping
# whatever it has run before. Same files, same order, both paths -- see the
# header of sql/bootstrap/00_schema_migration.sql.
#
# Everything happens in one transaction. If a file that was already applied
# has since been edited, nothing is applied and the script exits non-zero.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if ! db_is_reachable; then
  db_unreachable_hint
  exit 1
fi

cd "$REPO_ROOT"
exec "$(project_python)" -m src.migrations
