#!/usr/bin/env python
"""Refuse to let an APCIQ figure reach the repository through a Power BI file.

Run it before committing anything under powerbi/, and again before making the
repository public:

    .venv/Scripts/python.exe scripts/check_powerbi_project.py

WHY THIS EXISTS

A Power BI Project (.pbip) is plain text, which is what makes it committable at
all: the definition -- tables, relationships, DAX measures, pages, visuals --
carries no data. The row data lives in .pbi/cache.abf, which .gitignore
excludes.

But "the definition carries no data" is a property of how the file is USED, not
a guarantee of the format. Four ordinary authoring gestures put a real figure
into a versioned file:

    a slicer or filter left on a numeric value
    a conditional formatting threshold typed in by hand
    a visual title or text box quoting a number
    a filter step applied in Power Query, which lands in the M expression

None of those are mistakes in Power BI. They are mistakes HERE, because the
APCIQ licence printed on page 65 of every edition forbids reproduction of its
information "en tout ou en partie, directement ou indirectement", and this
repository is going public.

HOW IT CHECKS

Not by looking for numbers that look suspicious -- by comparing what is in the
files against what is actually in the database, the same way check-secrets.sh
compares tracked files against the real values in .env. A figure is reported
because it IS an APCIQ figure, not because it has the shape of one.

Section 5 is a positive control. A checker that always answers OK proves
nothing, so the script ends by planting a real figure in a file of its own and
confirming it finds it. If it does not, the clean verdict above is worthless
and the script says so.

Exit code 0 = clean, 1 = something must be fixed, or the check was incomplete.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# A Power BI Project is a folder tree, not a file, so it is recognised by the
# folder names Power BI Desktop creates rather than by an extension.
POWERBI_MARKERS = (".Report/", ".SemanticModel/", "powerbi/")

# Sections 2 and 3 scan what POWER BI WRITES, not what we write. A README under
# powerbi/ is prose someone composed and reread, and check-secrets.sh already
# covers the whole repository; scanning it here only produces collisions -- a
# year, an IP octet -- that train a reader to skip warnings. The files below
# are tool output that nobody rereads line by line, which is the whole reason
# this check exists.
GENERATED_SUFFIXES = {".json", ".tmdl", ".bim", ".pbir", ".pbism", ".pbip", ".dax", ".platform"}

# Formats whose contents cannot be read as text. They are never skipped in
# silence: each one is named in section 4, because a check that passes over
# what it cannot read gives a false guarantee (learned on 2026-08-22, when
# check-secrets.sh reported "59 files verified" having failed to open one).
OPAQUE_SUFFIXES = {".pbix", ".abf", ".png", ".jpg", ".jpeg", ".gif", ".ico"}

# Two thresholds, two severities, and the split is measured rather than tuned.
#
# A report definition is full of small integers that mean nothing: canvas sizes
# (1280, 720), positions, font sizes, percentages. Above 10 000 that stops
# being true -- no layout property is 487 500 -- so a match there is a figure,
# full stop. Between 100 and 9 999 a match may be a genuine sales count or may
# be a visual's width, so it is reported for a human to look at rather than
# silently dropped. Nothing is ignored without being named.
HARD_FLOOR = 10_000
SOFT_FLOOR = 100

# Thousands separators seen in the wild, INCLUDING the non-breaking space:
# the same amount written with a normal space and with U+00A0 is two different
# strings, and a replace on the first silently leaves the second (learned the
# hard way on the APCIQ parser, 2026-08-23).
SEPARATORS = " \u00a0\u202f,'"


def run(*args: str) -> str:
    return subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def numbers_in(text: str) -> set[int]:
    """Every integer the text contains, written any way a human writes one.

    Two passes on purpose. The first joins digit groups that a thousands
    separator split apart, so "487 500" and "487,500" are found as 487500. The
    second reads the digits as they lie, so "487500" is found too. A figure
    written either way is the same reproduction of the same fact.
    """
    found: set[int] = set()

    grouped = re.compile(r"\d{1,3}(?:[" + re.escape(SEPARATORS) + r"]\d{3})+")
    joined = grouped.sub(lambda m: re.sub(f"[{re.escape(SEPARATORS)}]", "", m.group()), text)

    for source in (joined, text):
        for run_of_digits in re.findall(r"\d+", source):
            # Long runs are ids, timestamps and hashes, not published figures.
            if len(run_of_digits) <= 9:
                found.add(int(run_of_digits))
    return found


def powerbi_candidates() -> list[Path]:
    """Files git would carry that belong to a Power BI report.

    Tracked files plus untracked ones that are not ignored -- so a cache.abf
    that slipped past .gitignore would be seen, which is the point.
    """
    listed = run("git", "ls-files", "--cached", "--others", "--exclude-standard")
    return [
        REPO_ROOT / line
        for line in listed.splitlines()
        if any(marker in line for marker in POWERBI_MARKERS)
    ]


# Every measure that is an APCIQ figure or is DERIVED from one. The licence
# covers reproduction "directement ou indirectement", so a monthly payment
# computed from a median price is in scope exactly as the price is. Census
# incomes are NOT here: Statistics Canada's licence expressly allows
# redistribution, and putting them in would blur a distinction this project
# spent J3.3 establishing.
FIGURE_SOURCES = """
    select median_price      from marts.fact_market
    union select average_price     from marts.fact_market
    union select sales_count       from marts.fact_market
    union select active_listings   from marts.fact_market
    union select days_on_market    from marts.fact_market
    union select median_price      from marts.fact_market_trailing_12m
    union select average_price     from marts.fact_market_trailing_12m
    union select sales_count       from marts.fact_market_trailing_12m
    union select active_listings   from marts.fact_market_trailing_12m
    union select days_on_market    from marts.fact_market_trailing_12m
    union select round(loan_amount)                     from marts.fact_mortgage_scenario
    union select round(insurance_premium)               from marts.fact_mortgage_scenario
    union select round(minimum_down_payment)            from marts.fact_mortgage_scenario
    union select round(monthly_payment_contract_rate)   from marts.fact_mortgage_scenario
    union select round(monthly_payment_qualifying_rate) from marts.fact_mortgage_scenario
    union select round(income_required_lower_bound)     from marts.fact_mortgage_scenario
    union select round(income_required_lower_bound)     from marts.fact_affordability
    union select round(income_shortfall)                from marts.fact_affordability
"""


def figures_from_database() -> "tuple[set[int], str | None]":
    """Every APCIQ-derived figure currently in marts. Never printed."""
    try:
        from src.db import connect
    except Exception as exc:                                # pragma: no cover
        return set(), f"cannot import src.db ({exc})"

    query = (
        f"select distinct v::bigint from ({FIGURE_SOURCES}) as t(v) "
        f"where v >= {SOFT_FLOOR}"
    )
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            return {row[0] for row in cur.fetchall()}, None
    except Exception as exc:
        first_line = str(exc).strip().splitlines()[0]
        return set(), f"database unreachable ({first_line})"


def main() -> int:
    failures = 0
    warnings = 0
    unreadable: list[Path] = []

    def ok(msg: str) -> None:
        print(f"  OK    {msg}")

    def fail(msg: str) -> None:
        nonlocal failures
        print(f"  FAIL  {msg}")
        failures += 1

    def warn(msg: str) -> None:
        nonlocal warnings
        print(f"  WARN  {msg}")
        warnings += 1

    candidates = powerbi_candidates()

    print("== 1. Files that must never be tracked ==")
    forbidden = {
        "cache.abf": "the whole imported dataset, APCIQ figures included",
        "localSettings.json": "local paths and connection details",
    }
    for name, what in forbidden.items():
        offenders = [p for p in candidates if p.name == name]
        if offenders:
            shown = ", ".join(str(p.relative_to(REPO_ROOT)) for p in offenders)
            fail(f"{name} is committable and holds {what}: {shown}")
        else:
            ok(f"no {name} among the files git would carry")

    new_pbix = [
        p for p in candidates
        if p.suffix.lower() == ".pbix" and p.name != "mhi_interest_rates.pbix"
    ]
    if new_pbix:
        shown = ", ".join(str(p.relative_to(REPO_ROOT)) for p in new_pbix)
        fail("a .pbix other than the J2 report is committable, and its data "
             f"cannot be inspected: {shown}")
    else:
        ok("no new .pbix among the files git would carry")

    print("\n== 2. APCIQ figures from the database, in the files Power BI generates ==")
    figures, why_not = figures_from_database()

    texts: "dict[Path, set[int]]" = {}
    opaque: list[Path] = []
    prose: list[Path] = []
    for path in candidates:
        suffix = path.suffix.lower()
        if suffix in OPAQUE_SUFFIXES:
            opaque.append(path)
        elif suffix not in GENERATED_SUFFIXES:
            prose.append(path)
        else:
            try:
                texts[path] = numbers_in(path.read_text(encoding="utf-8", errors="strict"))
            except Exception:
                unreadable.append(path)

    if why_not:
        warn(f"section skipped -- {why_not}")
        warn("open the tunnel (bash scripts/tunnel-start.sh) and run again; "
             "section 3 still runs, but section 2 is the strong one")
        failures += 1
    elif not candidates:
        ok("no Power BI file is committable yet, so there is nothing to compare")
    else:
        for path, numbers in texts.items():
            hits = numbers & figures
            hard = {n for n in hits if n >= HARD_FLOOR}
            soft = hits - hard
            rel = path.relative_to(REPO_ROOT)
            if hard:
                fail(f"{rel} holds {len(hard)} figure(s) matching APCIQ data above "
                     f"{HARD_FLOOR:,} -- values deliberately not printed here")
            if soft:
                warn(f"{rel} holds {len(soft)} number(s) matching APCIQ data between "
                     f"{SOFT_FLOOR} and {HARD_FLOOR:,}; a layout property can collide "
                     "with a genuine count, so look before deciding")
            if not hits:
                ok(f"{rel} matches no figure in the database")
        if not texts:
            ok("no readable Power BI text file to compare")

    print("\n== 3. Numbers large enough to be a price, whatever the database holds today ==")
    print("     (catches a figure from an edition not yet loaded, which section 2 cannot)")
    for path, numbers in texts.items():
        big = {n for n in numbers if 100_000 <= n <= 99_999_999}
        rel = path.relative_to(REPO_ROOT)
        if big:
            warn(f"{rel} holds {len(big)} number(s) in price range -- confirm each is "
                 "a layout value and not a figure")
        else:
            ok(f"{rel} holds no number in price range")
    if not texts:
        ok("no readable Power BI text file to scan")

    print("\n== 4. What sections 2 and 3 did NOT scan, and why ==")
    print("     (nothing is skipped in silence: a check that passes over what it")
    print("      cannot read gives a false guarantee)")
    for path in unreadable:
        fail(f"{path.relative_to(REPO_ROOT)} is Power BI output but could not be "
             "read as text -- unexpected, and it must be explained before committing")
    for path in opaque:
        warn(f"{path.relative_to(REPO_ROOT)} cannot be inspected at all: its format "
             "hides its contents. Whether it may be committed is a DECISION, not a "
             "result of this check")
    for path in prose:
        ok(f"{path.relative_to(REPO_ROOT)} is prose we wrote, not Power BI output; "
           "check-secrets.sh covers it")
    if not (unreadable or opaque or prose):
        ok("every candidate file was scanned")

    print("\n== 5. Positive control ==")
    if why_not:
        warn("cannot run -- no figure available to plant, so the verdict above has "
             "NOT been shown to work")
    else:
        planted = max(f for f in figures if f >= HARD_FLOOR)
        # Three written forms, and the third groups with U+00A0 rather than a
        # normal space. The two are different strings, and a scanner handling
        # only the first passes over the second in silence -- the bug that
        # broke a parser test on 2026-08-23. If any form is missed, the whole
        # verdict is declared worthless rather than quietly narrowed.
        grouped = f"{planted:,}"
        forms = [str(planted), grouped, grouped.replace(",", " ")]
        with tempfile.TemporaryDirectory() as tmp:
            # Written outside the repository on purpose: a real figure never
            # touches the working tree, not even for a second.
            probe = Path(tmp) / "planted.json"
            body = ",\n".join(f'  "v{i}": "{form}"' for i, form in enumerate(forms))
            probe.write_text("{\n" + body + "\n}", encoding="utf-8")
            seen = numbers_in(probe.read_text(encoding="utf-8"))
        if planted in seen:
            ok(f"a real figure planted in all {len(forms)} written forms (plain, "
               "comma-grouped, non-breaking-space-grouped) was found")
        else:
            fail("the checker did NOT find a figure it planted itself -- every OK "
                 "above is worthless")

    print()
    if failures:
        print(f"VERDICT: {failures} failure(s), {warnings} warning(s). Do not commit.")
        return 1
    if warnings:
        print(f"VERDICT: no failure, {warnings} warning(s) to look at before committing.")
        return 0
    print("VERDICT: clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
