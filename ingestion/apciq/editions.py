"""Which quarterly editions of the Baromètre exist, and where to find them.

Everything here was probed on 2026-08-23 with range requests (one kilobyte per
file, not the whole 7 MB), so the catalogue rests on responses rather than on
a remembered pattern.

WHAT WAS PROBED, AND WHAT CAME BACK
-----------------------------------
    https://com.apciq.ca/sam/pdf/bar/{YYYY}/{YYYYQQ}-bar-mtl.pdf

    2019 Q1              404      the archive starts after this
    2019 Q2 .. 2026 Q2   206      29 consecutive quarters, no gap
    2026 Q3, 2026 Q4     404      not published yet

HEAD is useless on this host: it answers 302 to everything, including URLs
that do not exist. Only a GET that follows redirects tells the truth, which is
why every probe below is a ranged GET.

THE -fr ALIAS IS NOT NEEDED
---------------------------
2025 Q3 and 2025 Q4 also answer on `-bar-mtl-fr.pdf`. Both spellings return a
file of exactly the same length (9 438 479 bytes for 2025 Q4), a few hours
apart in Last-Modified. It is the same document published twice, so the plain
spelling covers all 29 quarters and the code needs no second pattern. Recorded
here because the alias will look like a missing case to whoever reads this.

LICENCE -- READ BEFORE PUBLISHING ANYTHING BUILT ON THIS
--------------------------------------------------------
Page 65 of the PDF, verbatim:

    « Toute reproduction de l'information qui s'y retrouve, en tout ou en
      partie, directement ou indirectement, est strictement interdite sans
      l'autorisation préalable écrite du titulaire du droit d'auteur. »

Stricter than the website terms quoted in docs/data-sources.md section 2.1,
which allow non-commercial use with attribution. The safe reading is the
strict one: APCIQ figures stay inside the private database. No extracted value
belongs in a versioned file, a published dataset, or a report shared outside.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BASE_URL = "https://com.apciq.ca/sam/pdf/bar"

# 2019 Q1 answers 404. Verified, not assumed -- and the reason milestone J3
# runs from 2019 Q2 rather than the 2015 the original brief asked for.
FIRST_EDITION = (2019, 2)

LICENCE_URL = "https://apciq.ca/conditions-dutilisation/"
ATTRIBUTION = "Source : APCIQ par le système Centris"

# Where archived PDFs land. Relative to the repository root; data/ is
# gitignored, so nothing here is ever committed.
ARCHIVE_DIR = "data/apciq"


@dataclass(frozen=True, order=True)
class Edition:
    """One quarterly publication."""

    year: int
    quarter: int

    def __post_init__(self) -> None:
        if not 1 <= self.quarter <= 4:
            raise ValueError(f"quarter must be 1..4, got {self.quarter}")

    @property
    def code(self) -> str:
        """The token APCIQ puts in the filename: 202602 for 2026 Q2."""
        return f"{self.year}{self.quarter:02d}"

    @property
    def filename(self) -> str:
        return f"{self.code}-bar-mtl.pdf"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.year}/{self.filename}"

    def __str__(self) -> str:
        return f"{self.year} Q{self.quarter}"


def quarter_of(day: date) -> Edition:
    """The edition covering a calendar date."""
    return Edition(day.year, (day.month - 1) // 3 + 1)


def candidate_editions(today: date) -> list[Edition]:
    """Every quarter from the first archived one up to the current one.

    Candidates, not confirmed files. The most recent quarter is normally not
    published yet -- APCIQ releases a few weeks after quarter end -- so the
    downloader is expected to meet 404s at the tail and must tolerate them
    there. A 404 anywhere else is a hole in the archive and must not be.
    """
    first = Edition(*FIRST_EDITION)
    last = quarter_of(today)
    if last < first:
        return []

    out: list[Edition] = []
    year, quarter = first.year, first.quarter
    while (year, quarter) <= (last.year, last.quarter):
        out.append(Edition(year, quarter))
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return out
