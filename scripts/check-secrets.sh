#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# check-secrets.sh -- refuse to let a secret reach the repository.
#
# Run it before every commit, and again before making the repository public.
#
# It compares the files git would carry against the real values in .env. The
# secrets themselves are never printed, never passed on a command line, and
# never written anywhere: they are piped into grep on standard input, and only
# the NAME of an offending file is ever shown.
#
# Section 6 is a positive control. A checker that always answers OK proves
# nothing, so the script ends by looking for two strings it KNOWS are present.
# If it fails to find them, the clean result above is worthless and the script
# says so.
#
# Usage:  bash scripts/check-secrets.sh
# Exit code 0 = clean, 1 = something must be fixed before committing.
# ---------------------------------------------------------------------------
set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$REPO_ROOT"

FAILURES=0
WARNINGS=0
pass() { echo "  OK    $1"; }
fail() { echo "  FAIL  $1"; FAILURES=$((FAILURES + 1)); }

# Everything git would include: tracked files plus untracked ones that are not
# ignored. Ignored files are excluded on purpose -- that is the whole point of
# .env being ignored.
mapfile -t CANDIDATES < <(git ls-files --cached --others --exclude-standard)

# grep reads the needle from standard input, so a secret never appears in the
# process list; -l prints file names only, never the matching line.
in_files() { printf '%s\n' "$1" | grep -l -F -f - -- "${CANDIDATES[@]}" 2>/dev/null; }
in_history() { printf '%s\n' "$1" | grep -q -F -f - <(git log -p --all --no-color 2>/dev/null); }

echo "== 1. Files that must never be tracked =="
for path in .env .venv; do
  if git check-ignore -q "$path"; then
    pass "$path is in .gitignore"
  else
    fail "$path is NOT ignored by git"
  fi
  if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    fail "$path is currently TRACKED by git"
  fi
done

echo
echo "== 2. Secret values from .env must not appear in any candidate file =="
scan_files() {
  local label="$1" value="$2" hits
  [ -z "$value" ] && { echo "  SKIP  $label is not set in .env"; return; }
  hits="$(in_files "$value")"
  if [ -n "$hits" ]; then
    fail "$label appears in: $(echo "$hits" | tr '\n' ' ')"
  else
    pass "$label appears in no candidate file"
  fi
}
scan_files "VPS_HOST"          "$(env_get VPS_HOST || true)"
scan_files "POSTGRES_PASSWORD" "$(env_get POSTGRES_PASSWORD || true)"

echo
echo "== 3. Same check against the whole git history =="
scan_history() {
  local label="$1" value="$2"
  [ -z "$value" ] && { echo "  SKIP  $label is not set in .env"; return; }
  if in_history "$value"; then
    fail "$label is present somewhere in git history"
  else
    pass "$label is absent from git history"
  fi
}
scan_history "VPS_HOST"          "$(env_get VPS_HOST || true)"
scan_history "POSTGRES_PASSWORD" "$(env_get POSTGRES_PASSWORD || true)"

echo
echo "== 4. Private keys and credential-looking files =="
if git ls-files --cached --others --exclude-standard \
   | grep -Ei '(^|/)(id_(rsa|ed25519|ecdsa)|.*\.(pem|pfx|p12|key))$' ; then
  fail "a key-like file is in the candidate list (see above)"
else
  pass "no key-like file name"
fi
if grep -l -E 'BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY' -- "${CANDIDATES[@]}" 2>/dev/null; then
  fail "a private key block is embedded in the files listed above"
else
  pass "no private key block embedded in any file"
fi

echo
echo "== 5. Hard-coded network addresses =="
# 127.0.0.1 and 0.0.0.0 are allowed: they are the security model, not a leak.
LEAKS="$(grep -n -E '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' -- "${CANDIDATES[@]}" 2>/dev/null \
         | grep -v -E '127\.0\.0\.1|0\.0\.0\.0|255\.255' || true)"
if [ -n "$LEAKS" ]; then
  echo "$LEAKS" | sed 's/^/        /'
  fail "an IPv4 address other than loopback appears above -- check each one"
else
  pass "no hard-coded IPv4 address other than loopback"
fi

echo
echo "== 6. Files this scan could NOT look inside =="
# The most dangerous failure mode of a secret scanner is silence about what it
# could not read. A .pbix, a .zip or any compressed file stores its content
# compressed: grep finds nothing in it, and a clean verdict above says NOTHING
# about what is inside. Reporting them is not optional.
UNSCANNABLE=""
for path in "${CANDIDATES[@]}"; do
  [ -f "$path" ] || continue
  [ -s "$path" ] || continue
  grep -Iq . "$path" 2>/dev/null || UNSCANNABLE="$UNSCANNABLE $path"
done
if [ -n "$UNSCANNABLE" ]; then
  echo "  WARN  sections 2 to 5 did NOT look inside these files:"
  for path in $UNSCANNABLE; do
    echo "          $path"
  done
  echo "        They are binary or compressed. Verified on 2026-08-22 against a"
  echo "        .pbix: searching its extracted content for a string it certainly"
  echo "        contains found nothing, because the data model is compressed."
  echo "        Whatever is inside must be a conscious decision, not an omission."
  WARNINGS=1
else
  pass "every candidate file is text and was actually searched"
fi

echo
echo "== 7. Positive control: the checker must be able to find something =="
if [ -n "$(in_files mhi_pgdata)" ]; then
  pass "file scan detects a known-present string (mhi_pgdata)"
else
  fail "file scan did NOT detect a known-present string -- the scan above is broken"
fi
if in_history mhi-postgres; then
  pass "history scan detects a known-present string (mhi-postgres)"
else
  fail "history scan did NOT detect a known-present string -- the scan above is broken"
fi

echo
if [ "$FAILURES" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo "CLEAN -- ${#CANDIDATES[@]} files checked, all of them actually searched."
  exit 0
fi
if [ "$FAILURES" -eq 0 ]; then
  echo "NO LEAK FOUND in the files that could be searched, but section 6 lists"
  echo "files this scan cannot see inside. Read it before committing."
  exit 0
fi
echo "$FAILURES PROBLEM(S) FOUND -- do not commit until they are fixed."
exit 1
