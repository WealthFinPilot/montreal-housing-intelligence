"""Refuse to let an APCIQ figure reach a tracked file, directly or indirectly.

Page 65 of every Baromètre edition forbids reproducing its figures « en tout ou
en partie, directement ou **indirectement** ». That second word is what this
script exists for, and it is why a plain text search is not enough: a
price-to-income ratio multiplied by a published census income gives the price
back, and census income is redistributable under the Statistics Canada licence.

The rule, decided 2026-09-13: **a figure may appear in a tracked file only if it
cannot be inverted into an APCIQ price.**

Two checks, in decreasing confidence:

  1. DIRECT   -- every number of 5+ digits in a tracked file is compared against
                the APCIQ figures actually loaded in the database. This is a
                comparison to the data, not a guess. It FAILS the run.
  2. INDIRECT -- ratios written in the project's own notation (a decimal followed by x or ×)
                near the word "ratio" are reported for a human to explain. It
                WARNS, because the notation is also used for things that are
                not ratios at all.

What this script cannot see, written down so nobody mistakes silence for proof:
a price written in thousands ("578 k$"), a price spelled out in words, a figure
inside a binary file (section 6 of check-secrets.sh covers those separately),
and any arithmetic more elaborate than the ratio above.

Exit codes:  0 = clean,  1 = a figure must be removed,  2 = the database was
unreachable, so the check did NOT run,  3 = no figure found, but WARN lines
were printed and must be read. Until 2026-09-15 a warning exited 0, which let
check-secrets.sh print CLEAN over a ratio nobody had looked at.

Usage:  python scripts/check_apciq_figures.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Below this many digits the comparison is pure noise: years (2019), row counts
# (1136), sales counts and day counts all collide with something in a 24 795
# figure archive. APCIQ median and average prices are 6 or 7 digits, so 5 is a
# margin rather than a knife edge.
MIN_DIGITS = 5

# Amounts that legitimately appear in tracked files even though they collide
# with some APCIQ figure. Each one is a PUBLISHED REGULATORY constant or a
# parameter this project chose, never a figure read from a Baromètre.
#
# Like the apciq_known_publisher_defect seed, this list is a declaration, not a
# mute list: an entry that no longer appears anywhere is reported, because a
# waiver nobody re-examines is how a workaround becomes permanent.
DECLARED_EXCEPTIONS = {
    "300000": "upper bound of the down-payment what-if slider (a chosen value)",
    "400000": "FCAC worked example of the minimum down payment",
    "500000": "first tranche of the minimum down payment (FCAC)",
    "600000": "FCAC worked example of the minimum down payment",
    "1000000": "maximum insurable price up to 80 % LTV (CMHC)",
    "1500000": "maximum insurable price above 80 % LTV (CMHC)",
    "95000": "opening position of the down-payment slider (a chosen value)",
    "360000": "highest CT median INCOME of sector 9 -- StatCan, redistributable",
    "487500": "worked example in check_powerbi_project.py, chosen for NOT being "
              "a layout value",
    "529000": "fictional listing price in the original brief, section 13",
    "509000": "fictional listing price in the original brief, section 13",
    "499000": "fictional listing price in the original brief, section 13",
}

# A thousands separator is a space, or a comma followed by exactly three digits.
# Anything looser splices a quarter label into the amount after it and invents a
# six-digit number that was never written. Observed on 2026-09-13, by this
# script, on its first run -- and the invented number turned out to be a real
# APCIQ figure, so the checker failed on its own comment.
NUMBER = re.compile(r"\b\d{1,3}(?:[   ,]\d{3})+\b|\b\d{4,}\b")

# In a .csv the comma is a field boundary, so joining across one fabricates a
# number out of two adjacent columns. Spaces only there.
NUMBER_CSV = re.compile(r"\b\d{1,3}(?:[   ]\d{3})+\b|\b\d{4,}\b")
RATIO_NOTATION = re.compile(r"\b(\d{1,2}[.,]\d+)\s*[x×]")

# The window a price-to-income ratio occupies. Below it, the same notation means
# a relative-price axis, a CPI factor or a reconciliation multiple; above it, a
# percentage. Neither inverts into a price. Measured maximum in the archive on
# 2026-08-30: 45.5. If a slice ever goes past the ceiling, move the ceiling --
# do not widen it on a hunch.
RATIO_FLOOR = 4.0
RATIO_CEILING = 60.0
TEXT_SUFFIXES = {
    ".md", ".sql", ".py", ".yml", ".yaml", ".json", ".sh", ".txt",
    ".cfg", ".ini", ".toml", ".dax", ".csv",
}

# Not searched, and saying so IS the point -- the same discipline as section 6
# of check-secrets.sh. These hold extracts of sources whose licence explicitly
# allows redistribution (Statistics Canada; Ville de Montreal / MAMH). Their
# figures collide with the APCIQ archive by coincidence of magnitude, not by
# provenance: a six-digit assessment value is demonstrably not a Barometre price.
#
# This is only safe because of a separate repository rule: no APCIQ data file is
# tracked at all -- the 29 PDFs and the hand-read oracle live outside git. If
# that rule ever changes, this exclusion has to go first.
EXCLUDED_DIRS = ("sample_data/",)


def digits_of(token: str) -> str:
    """Strip every separator, keep the digits. '400 000' and '400,000' -> '400000'."""
    return re.sub(r"[^\d]", "", token)


def tracked_text_files() -> tuple[list[Path], list[str]]:
    """Everything git would carry, split into what is searched and what is not."""
    # -z and an explicit UTF-8 decode, both needed. Without -z git quotes any
    # path holding a non-ASCII byte ("docs/fr/M\303\251thode.md"), that name
    # opens no file, and `not path.is_file()` below dropped it without a word.
    # Without the encoding, Windows decodes git's UTF-8 output as cp1252 and
    # mangles the same names a second way. docs/fr/ exists since 2026-09-15.
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        check=True,
    )
    searched: list[Path] = []
    skipped: list[str] = []
    for line in out.stdout.split("\0"):
        if not line:
            continue
        path = REPO_ROOT / line
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        if line.startswith(EXCLUDED_DIRS):
            skipped.append(line)
            continue
        searched.append(path)
    return searched, skipped


# Why the check could not run, when it could not. An import error and a closed
# tunnel are not the same failure, and telling a reader to open the tunnel when
# psycopg is simply missing sends them to the wrong place -- which is what
# happened on 2026-09-15, with the tunnel already open.
SKIP_REASON = ""


def load_apciq_figures() -> set[str] | None:
    """The figures actually in the database. None when it cannot be reached."""
    global SKIP_REASON
    try:
        from src.db import connect
    except Exception as exc:
        SKIP_REASON = (
            f"{type(exc).__name__}: {exc}\n"
            "        This is the interpreter, not the tunnel. Run the check with "
            "the project venv:\n"
            "        .venv/Scripts/python.exe scripts/check_apciq_figures.py"
        )
        return None
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select distinct value_text
                    from raw.apciq_barometer_statistic
                    where value_text is not null
                    """
                )
                figures = set()
                for (value,) in cur.fetchall():
                    token = digits_of(value)
                    if len(token) >= MIN_DIGITS:
                        figures.add(token)
            conn.rollback()
        return figures
    except Exception as exc:
        SKIP_REASON = f"{type(exc).__name__}: {exc}"
        return None


def _in_ratio_window(token: str) -> bool:
    value = float(token.replace(",", "."))
    return RATIO_FLOOR <= value <= RATIO_CEILING


def _looks_like_a_level_ratio(line: str) -> bool:
    """A decimal inside the ratio window, written as a multiple or named as one."""
    for match in RATIO_NOTATION.finditer(line):
        if _in_ratio_window(match.group(1)):
            return True
    # A table cell can carry the ratio without the multiplier sign, so the
    # measure name has to count as well -- that is how the 2026-09-02 debt hid.
    if re.search(r"price[ -]to[ -]income", line, re.IGNORECASE):
        # A decimal followed by a percent sign is a share or a change,
        # never a multiple of income.
        for match in re.finditer(r"\b\d{1,2}[.,]\d+\b(?!\s*(?:%|pts|points|point))", line):
            if _in_ratio_window(match.group()):
                return True
    return False


def main() -> int:
    figures = load_apciq_figures()
    if figures is None:
        print("  SKIP  APCIQ figure check did NOT run.")
        if SKIP_REASON:
            print(f"        {SKIP_REASON}")
        print("        Open the tunnel (bash scripts/tunnel-start.sh) and run again")
        print("        BEFORE making this repository public. A clean verdict from")
        print("        the other sections says nothing about APCIQ figures.")
        return 2

    files, skipped = tracked_text_files()
    leaks: list[tuple[Path, int, str, str]] = []
    seen_exceptions: set[str] = set()
    ratio_notes: list[tuple[Path, int, str]] = []

    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            pattern = NUMBER_CSV if path.suffix.lower() == ".csv" else NUMBER
            for match in pattern.finditer(line):
                token = digits_of(match.group())
                if len(token) < MIN_DIGITS:
                    continue
                if token in DECLARED_EXCEPTIONS:
                    seen_exceptions.add(token)
                    continue
                if token in figures:
                    leaks.append(
                        (path, lineno, match.group(), line.strip()[:100])
                    )
            if _looks_like_a_level_ratio(line):
                ratio_notes.append((path, lineno, line.strip()[:100]))

    print(f"  ..    {len(figures)} APCIQ figures of {MIN_DIGITS}+ digits loaded; "
          f"{len(files)} tracked text files searched")
    if skipped:
        print(f"  ..    {len(skipped)} file(s) deliberately NOT searched "
              f"(redistributable source data):")
        for line in skipped:
            print(f"          {line}")

    status = 0
    if leaks:
        print(f"  FAIL  {len(leaks)} APCIQ figure(s) found in tracked files:")
        for path, lineno, token, context in leaks:
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"          {rel}:{lineno}  {token!r}")
            print(f"            {context}")
        print("        Remove them. The licence forbids reproduction in whole or")
        print("        in part, directly or indirectly.")
        status = 1
    else:
        print("  OK    no APCIQ figure of 5+ digits in any tracked text file")

    stale = sorted(set(DECLARED_EXCEPTIONS) - seen_exceptions)
    if (stale or ratio_notes) and status == 0:
        status = 3
    if stale:
        print("  WARN  declared exception(s) that appear nowhere any more:")
        for token in stale:
            print(f"          {token} -- {DECLARED_EXCEPTIONS[token]}")
        print("        Remove the entry, or find out why the figure left.")

    if ratio_notes:
        print(f"  WARN  {len(ratio_notes)} line(s) write a ratio in level notation.")
        print("        A price-to-income ratio times a published census income")
        print("        gives an APCIQ price back. Each one must be a ratio of two")
        print("        ratios, a factor, or something that is not a price at all:")
        for path, lineno, context in ratio_notes:
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"          {rel}:{lineno}  {context}")

    return status


if __name__ == "__main__":
    sys.exit(main())
