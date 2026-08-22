#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# prove-quality-gate.sh -- show that the dbt tests actually catch a bad value.
#
# Acceptance criterion 3 of milestone J2 asks for more than green tests: it
# asks for proof that a test FAILS when a source row is corrupted. A control
# that has never caught anything proves nothing.
#
# What this does, in order:
#   1. picks the most recent policy-rate observation and shows its value
#   2. overwrites it in raw with a string that is not a number
#   3. runs dbt test and requires it to FAIL, naming the tests that caught it
#   4. repairs the row by re-running the ingestion pipeline
#   5. runs dbt test again and requires it to PASS
#
# Step 4 is not just cleanup. It proves the revision path: the pipeline notices
# that the stored value no longer matches the source and reports exactly one
# update -- the same mechanism that will pick up a genuine Bank of Canada
# revision.
#
# This script writes to the database and repairs itself. If it is interrupted
# between steps 2 and 4, restore the row with:
#     .venv/Scripts/python.exe -m ingestion.bank_of_canada.run
#
# Usage:  bash scripts/prove-quality-gate.sh
# ---------------------------------------------------------------------------
set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$REPO_ROOT"

PY="$REPO_ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$REPO_ROOT/.venv/bin/python"
export PYTHONIOENCODING=utf-8

LOG="$REPO_ROOT/dbt/logs/quality-gate.log"
mkdir -p "$(dirname "$LOG")"

if ! tunnel_is_up; then
  echo "FAIL: the SSH tunnel is closed. Run: bash scripts/tunnel-start.sh" >&2
  exit 1
fi

FAILURES=0
step() { echo; echo "=== $1 ==="; }

# dbt colours its output, which puts an escape sequence in front of every line.
# Strip it before matching, otherwise a pattern anchored at the start of a line
# can never match -- learned the hard way on 2026-08-22.
plain() { sed 's/\x1b\[[0-9;]*m//g' "$1"; }

step "1. Before -- the row we are about to break"
"$PY" - <<'PYEOF'
from src import db
with db.connect() as conn, conn.cursor() as cur:
    cur.execute("""
        SELECT series_id, observation_date, value_raw
          FROM raw.boc_observation
         WHERE series_id = 'V39079'
         ORDER BY observation_date DESC
         LIMIT 1
    """)
    print("   raw.boc_observation :", cur.fetchone())
    cur.execute("""
        SELECT rate_percent
          FROM staging.stg_bank_of_canada__interest_rates
         WHERE series_id = 'V39079'
         ORDER BY observation_date DESC
         LIMIT 1
    """)
    print("   staging view        : rate_percent =", cur.fetchone()[0])
PYEOF

step "2. Corrupting that one value in the raw layer"
"$PY" - <<'PYEOF'
from src import db
with db.connect() as conn, conn.cursor() as cur:
    cur.execute("""
        UPDATE raw.boc_observation
           SET value_raw = 'not-a-number'
         WHERE series_id = 'V39079'
           AND observation_date = (
               SELECT max(observation_date) FROM raw.boc_observation WHERE series_id = 'V39079'
           )
        RETURNING observation_date, value_raw
    """)
    print("   set to:", cur.fetchone())
    conn.commit()
PYEOF

step "3. dbt test must now FAIL"
if bash "$REPO_ROOT/scripts/dbt.sh" test --select stg_bank_of_canada__interest_rates > "$LOG" 2>&1; then
  echo "   UNEXPECTED: dbt test passed on corrupted data. The tests are not doing their job."
  FAILURES=$((FAILURES + 1))
else
  echo "   dbt test failed, as required:"
  plain "$LOG" | grep -E "FAIL [0-9]+|Failure in test|Done\." | sed 's/^/      /' || true
fi

step "4. Repairing by re-running the ingestion pipeline"
"$PY" -m ingestion.bank_of_canada.run 2>&1 | grep -E "^(received|loaded)" | sed 's/^/   /'

step "5. dbt test must PASS again"
if bash "$REPO_ROOT/scripts/dbt.sh" test --select stg_bank_of_canada__interest_rates > "$LOG" 2>&1; then
  plain "$LOG" | grep -E "Done\." | sed 's/^/   /'
else
  echo "   UNEXPECTED: dbt test still fails after repair."
  plain "$LOG" | tail -20 | sed 's/^/      /'
  FAILURES=$((FAILURES + 1))
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "PROVEN: the quality gate catches a corrupted value, and the pipeline repairs it."
  exit 0
fi
echo "$FAILURES PROBLEM(S) -- the quality gate is not trustworthy as it stands."
exit 1
