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
# Section 9 is a positive control. A checker that always answers OK proves
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
#
# -z, and NUL-delimited reading, are not a detail. Without it git quotes any
# path holding a byte outside ASCII -- docs/Methode.md with an accent comes
# back as "docs/M\303\251thode.md", quotes included -- and that name opens
# no file. Sections 2 to 5 would skip it silently AND section 7, whose whole
# job is to name what could not be read, would not see it either: the run
# would print CLEAN over a file nobody ever opened. No tracked path is
# accented today; one file named after a Montreal place would be enough.
mapfile -d '' -t CANDIDATES < <(git ls-files -z --cached --others --exclude-standard)

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
#
# The address this check exists for is the VPS: it is PUBLIC, it is in .env,
# and it must never reach a tracked file.
#
# 127.0.0.1 and 0.0.0.0 are allowed: they are the security model, not a leak.
#
# RFC 1918 private ranges (10/8, 172.16/12, 192.168/16) and the link-local
# 169.254/16 are reported but do not fail the run. Since J4.3 the repository
# documents a Docker bridge gateway (172.18.0.1) and the subnet an SSH key is
# restricted to -- addresses that are identical on millions of machines, that
# locate nothing and grant nothing, and without which the orchestration cannot
# be understood. Failing on those would have made this check noise, and a check
# that is routinely overridden stops being a check. They are still PRINTED, so
# a new one has to be looked at.
# -o, so that every ADDRESS is judged on its own instead of the line holding
# it. Judging lines was wrong in the one case this check exists for: -v drops
# the whole matched line, so a public address written next to 127.0.0.1 -- the
# shape every tunnel script in this repository uses, "127.0.0.1:15432 to the
# server" -- was thrown away with the loopback and never reported. The same
# defect sat one storey up: a line carrying a private AND a public address was
# filed as private and did not fail the run. The positive control of
# 2026-09-13 passed because its address sat alone on its line.
#
# With -o each output line is path:lineno:ADDRESS, so the patterns below anchor
# on ":ADDRESS$" and classify the address, never its surroundings. It also
# stops the check from printing the surrounding text, which is a small bonus.
# PCRE lookarounds, because \b does not stop at a dot: in the StatCan cube
# coordinate 13.2.0.0.0.0.0.0.0.0 the first four fields look exactly like an
# address. Those were passing only because the sequence contains 0.0.0.0 and
# the old line-wide -v threw the whole line away -- one defect was cancelling
# the other, and fixing the -v alone surfaced six of them.
#
# An address is four fields not touching a fifth one: no digit and no
# "digit-dot" before it, no digit and no "dot-digit" after it. The first
# version refused ANY dot on either side, and so missed the most ordinary case
# of all, an address ending a sentence with its full stop -- found by the
# security review of 2026-09-16. A full stop is not a fifth field. (No example
# address is written here: this check fails on its own comments, as it should.)
ADDR_RE='(?<!\d)(?<!\d\.)(\d{1,3}\.){3}\d{1,3}(?!\d)(?!\.\d)'
PRIVATE_RE=':(10\.([0-9]{1,3}\.){2}[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|169\.254\.[0-9]{1,3}\.[0-9]{1,3})$'
ALLOWED_RE=':(127\.0\.0\.1|0\.0\.0\.0|255\.255\.[0-9]{1,3}\.[0-9]{1,3})$'

FOUND="$(grep -H -n -o -P "$ADDR_RE" -- "${CANDIDATES[@]}" 2>/dev/null \
         | grep -v -E "$ALLOWED_RE" || true)"
PRIVATE_HITS="$(printf '%s' "$FOUND" | grep -E "$PRIVATE_RE" || true)"
PUBLIC_HITS="$(printf '%s' "$FOUND" | grep -v -E "$PRIVATE_RE" || true)"

if [ -n "$PRIVATE_HITS" ]; then
  echo "        -- private ranges (RFC 1918 / link-local), reported not refused:"
  echo "$PRIVATE_HITS" | sed 's/^/        /'
fi
if [ -n "$PUBLIC_HITS" ]; then
  echo "        -- PUBLIC addresses:"
  echo "$PUBLIC_HITS" | sed 's/^/        /'
  fail "a PUBLIC IPv4 address appears above -- that is what this check is for"
elif [ -n "$PRIVATE_HITS" ]; then
  pass "no public IPv4 address; the private ones above are listed for review"
else
  pass "no hard-coded IPv4 address other than loopback"
fi

echo
echo "== 6. APCIQ figures, directly or indirectly =="
# The APCIQ licence forbids reproduction "en tout ou en partie, directement ou
# indirectement". A text search for a secret cannot see that, because the figure
# is not a secret -- it is a number that must not be redistributed. The check
# lives in its own script because it needs the database to know what those
# numbers actually are, rather than guessing from a pattern.
#
# It needs the tunnel open. When it cannot reach the database it says so and
# does NOT pass silently: a clean verdict from sections 1 to 5 says nothing
# about APCIQ figures.
# The PROJECT venv first, never a python that merely exists on PATH. On
# 2026-09-15 the global interpreter was picked, had no psycopg, and the check
# reported "database unreachable" with the tunnel wide open -- a guard that
# never ran and blamed the wrong thing. Same order as scripts/dbt.sh.
if [ -x .venv/Scripts/python.exe ]; then
  PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  PY=python3
fi
APCIQ_OUT="$("$PY" scripts/check_apciq_figures.py 2>&1)"
APCIQ_RC=$?
echo "$APCIQ_OUT"
# 3 = WARN lines to read. It used to be 0, and the banner said CLEAN over them.
case "$APCIQ_RC" in
  0) : ;;
  2|3) WARNINGS=1 ;;
  *) FAILURES=$((FAILURES + 1)) ;;
esac

echo
echo "== 7. Files this scan could NOT look inside =="
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
echo "== 8. Private context: terms that belong to no published file =="
# This repository documents a data project and nothing else. The terms that
# must never reach it are read from a list kept in .git/info/, never tracked:
# publishing the list would publish what it protects. This section checks the
# files git would carry; before any history is published, run the same script
# with --history on it, because a term removed today is still in the commit
# that added it.
TERMS_OUT="$("$PY" scripts/check_publication_terms.py 2>&1)"
TERMS_RC=$?
echo "$TERMS_OUT"
case "$TERMS_RC" in
  0) : ;;
  2) WARNINGS=1 ;;
  *) FAILURES=$((FAILURES + 1)) ;;
esac

echo
echo "== 9. Positive control: the checker must be able to find something =="
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
  # Not "section 7" by name: sections 6 and 8 raise warnings too -- a skipped
  # check, a ratio in level notation -- and pointing at 7 alone hid them.
  echo "NO LEAK FOUND in the files that could be searched, but WARN or SKIP lines"
  echo "above (sections 6, 7 or 8) must be read before committing."
  exit 0
fi
echo "$FAILURES PROBLEM(S) FOUND -- do not commit until they are fixed."
exit 1
