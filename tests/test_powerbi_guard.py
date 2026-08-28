"""The number reader that stands between an APCIQ figure and a public commit.

`check_powerbi_project.py` compares the numbers found in Power BI's generated
files against the figures actually in the database. Everything it can promise
rests on `numbers_in()` finding a figure however it happens to be written --
and a report file can write the same amount four different ways depending on
where it landed: a filter value, a title, a formatted label, a Power Query
step.

The script carries its own positive control, which plants a real figure and
confirms it is found. That control proves the pipeline is wired; it does not
pin the behaviour down, and it cannot run at all when the database is
unreachable. These tests do both.

No database needed: this is pure string handling.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_powerbi_project", REPO_ROOT / "scripts" / "check_powerbi_project.py"
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

# Not a real figure from the archive, and deliberately not one: this file is
# tracked, and the rule since J3.2 is that no APCIQ figure enters a tracked
# file. 487531 is a shape, not a transcription -- it ends in an odd digit no
# published median would.
AMOUNT = 487531


@pytest.mark.parametrize(
    "written, why",
    [
        ("487531", "bare, as a JSON filter value"),
        ("487,531", "comma-grouped, as an English label"),
        ("487 531", "grouped with U+00A0, as a French label"),
        ("487 531", "grouped with a narrow no-break space"),
        ("487 531", "grouped with an ordinary space"),
        ('{"value": 487531}', "inside JSON"),
        ('"Median price 487,531 $"', "inside a visual title"),
        ("Table.SelectRows(S, each [p] = 487531)", "inside a Power Query step"),
    ],
)
def test_a_figure_is_found_however_it_is_written(written: str, why: str) -> None:
    """Every form a report file can carry the same amount in."""
    assert AMOUNT in guard.numbers_in(written), why


def test_the_non_breaking_space_is_not_quietly_missed() -> None:
    """The exact bug that broke a parser test on 2026-08-23.

    A normal space and U+00A0 are different strings. Code that handles the
    first and not the second does not fail -- it passes over the second in
    silence, which is worse, because the verdict still reads clean.
    """
    ordinary = guard.numbers_in("487 531")
    non_breaking = guard.numbers_in("487 531")
    assert ordinary == non_breaking == {487531, 487, 531}


def test_grouping_never_loses_the_ungrouped_reading() -> None:
    """"487,531" must yield the joined figure AND its parts.

    Both readings are kept on purpose. If a file happens to hold two unrelated
    numbers side by side, joining them could invent a figure that is not there
    -- so the parts are reported too, and the caller decides. A guard that
    reports too much is examined; a guard that reports too little is trusted.
    """
    assert guard.numbers_in("487,531") == {487531, 487, 531}


def test_identifiers_and_timestamps_are_not_read_as_figures() -> None:
    """Runs of digits longer than nine are ids, hashes and epoch millis.

    Without this, every report file would flag its own GUIDs and the warnings
    would be ignored within a week.
    """
    found = guard.numbers_in('{"id": "1756312800000", "guid": "12345678901234"}')
    assert 1756312800000 not in found
    assert 12345678901234 not in found


def test_layout_values_are_read_but_stay_below_the_hard_floor() -> None:
    """A canvas size is a number, and it must not be able to raise a failure.

    The guard reads them -- it hides nothing -- but only matches at or above
    HARD_FLOOR are treated as figures. This is what keeps a report full of
    positions and widths from producing a wall of false failures.
    """
    found = guard.numbers_in('{"width": 1280, "height": 720, "x": 0, "y": 40}')
    assert {1280, 720, 40}.issubset(found)
    assert not [n for n in found if n >= guard.HARD_FLOOR]


def test_a_price_sized_number_clears_the_hard_floor() -> None:
    """The counterpart of the test above: the floor still lets a price through."""
    assert AMOUNT >= guard.HARD_FLOOR


def test_generated_and_opaque_suffixes_do_not_overlap() -> None:
    """A file must not be both scanned and declared unscannable.

    Section 4 of the script reports every candidate it did not scan. If a
    suffix appeared in both sets, a file would be scanned and ALSO reported as
    skipped, and the section that exists to prevent silent gaps would start
    producing noise instead.
    """
    assert not (guard.GENERATED_SUFFIXES & guard.OPAQUE_SUFFIXES)
    assert ".pbix" in guard.OPAQUE_SUFFIXES
    assert ".tmdl" in guard.GENERATED_SUFFIXES
