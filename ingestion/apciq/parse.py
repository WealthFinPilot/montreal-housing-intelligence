"""Read Tableau 2 of a Baromètre page. Pure: no HTTP, no database, no clock.

WHAT THIS READS, AND WHAT IT LEAVES
-----------------------------------
Each island or sector page carries three tables. This module reads Tableau 2,
"Statistiques Centris détaillées par catégories de propriétés": three property
categories x five metrics x three periods.

    categories   Unifamiliale, Copropriété, Plex (2 à 5 logements)
    metrics      sales, active listings, median price, average price,
                 average days on market
    periods      the quarter, the trailing 12 months, and a 5-year change

Tableau 1 (Total résidentiel) is deliberately not read. It is the only place
new listings and sales volume appear, but only for all categories combined --
a grain that cannot enter fact_market, whose rows are quarter x geography x
property type. Recorded as a known gap in docs/apciq.md rather than half-done.
Tableau 3 (market conditions by price band) is likewise left for later.

THE PROBLEM: THERE IS NO TABLE IN THIS PDF
------------------------------------------
The Baromètre is a Power BI export. There is no table structure, no ruling
lines, only text boxes at absolute positions, and extract_text() interleaves
the columns into an unreadable stream. Position is the only thing that says
what a number means.

Three things about that position are NOT stable, and each of them broke an
earlier version of this parser:

  1. The page size changed. 1008 x 612 pt until 2025 Q2, 3825 x 2340 pt from
     2025 Q3 -- a factor of 3.8. Every coordinate here is therefore a fraction
     of page width or height, never a point measurement.

  2. The columns are not in the same place from one edition to the next. Their
     positions were measured on three editions and then found to be wrong on
     at least five others: in 2021 Q4 the whole of Tableau 2 sits noticeably
     further left. Fixed column bands, however carefully measured, are the
     wrong tool. So the columns are CALIBRATED from each edition, below.

  3. Within one row, a cell can be typeset up to 0.003 of a page above or
     below its own label. Grouping characters by vertical proximity therefore
     drops cells silently. The label anchors the row instead.

HOW THE COLUMNS ARE FOUND
-------------------------
Per PAGE -- not per edition. Power BI sizes each table to its own content, so
the 2021 Q4 island page puts its first column at 0.581 of the page width while
its Villeray page puts the same column at 0.542. Two passes:

  * Pass one splits every data row into runs of adjacent cell characters. The
    split threshold is not a constant -- it is twice the median character
    width OF THAT ROW, so it scales with the font and survives the page-size
    change. Measured margins: gaps inside a cell run to about half a character
    width; gaps between cells are ten times that.

  * Rows that show all five cells then vote: the median centre of each of the
    five runs becomes that page column anchor. Every cell of every row is then
    attributed to its nearest anchor.

Cells are attributed rather than cut out, so nothing can fall between two
bands and vanish. A run further than half a column spacing from every anchor
stops the edition instead.

WHAT THE PDF SAYS THESE NUMBERS MEAN
------------------------------------
From the "Définitions et notes explicatives" page, verbatim:

  * variation rates -- « En raison du caractère saisonnier des indicateurs
    liés au marché immobilier, les taux de variation sont calculés par rapport
    au même trimestre de l'année précédente. » So a change is year-over-year,
    never quarter-over-quarter.
  * median price -- « Valeur médiane des ventes effectuées au cours de la
    période visée. » A SALE price. Not an asking price, not an assessment.
  * active listings -- « Nombre d'inscriptions dont le statut est en vigueur
    le dernier jour du mois. Les données trimestrielles et annuelles
    correspondent à la moyenne des données mensuelles pour la période visée. »
    An average of month-end counts, so it must never be summed over time.
  * sales -- « La date de vente est celle de l'acceptation de la promesse
    d'achat », not the notarised date.
  * days on market -- « Nombre moyen de jours entre la date de signature du
    contrat de courtage et la date de vente. »

The same page carries a warning worth repeating wherever these figures are
shown: « les prix moyens et médians [...] ne reflètent pas nécessairement la
valeur moyenne ou médiane de l'ensemble des propriétés d'un Secteur. »
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from ingestion.apciq.editions import Edition

# --- layout, in fractions of the page ---------------------------------------

TITLE_MAX_Y = 0.045          # the page title lives in the top strip
TITLE_MAX_X = 0.55

# The Tableau 2 area. Its left edge keeps Tableau 1 out: on every edition seen,
# Tableau 1 stops before 0.34 and the Tableau 2 row labels start after 0.36.
TABLE2_MIN_X = 0.355
TABLE2_MIN_Y = 0.08
TABLE2_MAX_Y = 0.70

# No row label reaches further right than this. The leftmost figure column
# seen on any archived edition starts at 0.542 (2021 Q4, Villeray page), so
# 0.52 separates label from figures everywhere without touching a cell.
LABEL_MAX_X = 0.52

# Characters typeset as one piece of text share an exact top; 0.002 absorbs
# rounding. Used to find lines of TEXT -- labels and headings -- and never to
# group figures, which is the mistake this constant exists to avoid.
LABEL_LINE_TOLERANCE = 0.002

# A figure this close to a row label belongs to that row. Row pitch is 0.0225
# and a cell strays by at most 0.003, so 0.008 cannot reach a neighbour.
ROW_WINDOW = 0.008

# Two cell characters belong to the same cell when the gap between them is
# under this many character widths. Expressed in character widths so it scales
# with the font: the same rule works on a 1008 pt page and a 3825 pt one.
RUN_GAP_IN_CHAR_WIDTHS = 2.0

# Calibration needs rows that show all five cells. It happens PER PAGE,
# because Power BI sizes each table to its own content: on the 2021 Q4
# edition the island page puts its first column at 0.581 of the page width
# and the Villeray page puts it at 0.542. Six candidate rows exist per page
# (median and average price, three categories); three is the floor.
MIN_ROWS_FOR_CALIBRATION = 3

# A run must sit within this fraction of the column spacing of its anchor.
COLUMN_MATCH_FRACTION = 0.5

# Words that mark a period heading ("2e trimestre 2026", "12 derniers mois",
# "Depuis 5 ans"). Those lines carry digits and must not be read as data.
PERIOD_HEADER_WORDS = ("trimestre", "derniers", "Depuis")

# --- what the labels mean ----------------------------------------------------

# Order matters. "Délai de vente moyen (jours)" -- the 2019 and 2022 wording --
# contains both "jours" and "moyen", and it is the days-on-market row, not the
# average-price row. The 2026 wording is "Moyenne de jours sur le marché".
# The wording changed; the meaning did not. That is precisely why the verbatim
# label is stored alongside the code.
METRIC_RULES: tuple[tuple[str, str], ...] = (
    ("jours", "days_on_market"),
    ("médian", "median_price"),
    ("moyen", "average_price"),
    ("Inscriptions", "active_listings"),
    ("Ventes", "sales"),
)
METRIC_CODES = tuple(code for _, code in METRIC_RULES)

CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("Unifamiliale", "single_family"),
    ("Copropri", "condo"),
    ("Plex", "plex"),
)
CATEGORY_CODES = tuple(code for _, code in CATEGORY_RULES)

# The five cells of a row, left to right, and the period each pair belongs to.
COLUMN_NAMES = (
    "quarter_value",
    "quarter_change",
    "trailing_value",
    "trailing_change",
    "five_year_change",
)
COLUMN_COUNT = len(COLUMN_NAMES)

PERIODS: tuple[tuple[str, str | None, str], ...] = (
    ("quarter", "quarter_value", "quarter_change"),
    ("trailing_12m", "trailing_value", "trailing_change"),
    ("five_year", None, "five_year_change"),
)

SECTOR_RE = re.compile(r"Secteur\s*(\d+)\s*:")
ISLAND_LABEL = "Île de Montréal"
ISLAND_AREA_CODE = "island"
SECTOR_COUNT = 18            # the island's share of the 51 metro sectors

# Characters a Baromètre cell may legitimately contain. Everything else --
# trend arrows, the Wingdings glyphs the older exports use for them, the
# letters of the row label -- is not part of a figure. Non-breaking spaces are
# turned into ordinary ones first so that "123 456 $" survives as written.
SPACE_LIKE = "    \t"
KEEPABLE = set("0123456789-*$%,. ")


class SourceLayoutError(Exception):
    """The PDF is not shaped the way this parser expects.

    Raised rather than returning partial data. A positional parser that
    quietly skips what it cannot place is the worst possible outcome here: it
    produces a table that looks complete and is short a sector.
    """


@dataclass(frozen=True)
class Observation:
    """One cell pair of Tableau 2: a figure and its year-over-year change."""

    edition_year: int
    edition_quarter: int
    area_code: str               # 'island' or 'sector-07'
    property_category: str       # 'single_family' | 'condo' | 'plex'
    metric_code: str             # 'sales' | 'median_price' | ...
    period_code: str             # 'quarter' | 'trailing_12m' | 'five_year'
    value_text: str | None       # verbatim, e.g. '123 456 $' or '**'
    change_percent_text: str | None
    source_area_label: str
    source_category_label: str
    source_metric_label: str
    source_page: int


@dataclass(frozen=True)
class Run:
    """One cell as found on the page: its extent and its text."""

    x_start: float
    x_end: float
    text: str

    @property
    def centre(self) -> float:
        return (self.x_start + self.x_end) / 2


@dataclass(frozen=True)
class RowScan:
    """One data row of one page, before its cells are attributed to columns."""

    page_number: int
    area_code: str
    area_label: str
    category: str
    category_label: str
    metric: str
    metric_label: str
    runs: tuple[Run, ...]


# --- character handling ------------------------------------------------------


def clean_cell(text: str) -> str | None:
    """Keep what a Baromètre cell can contain; drop the rest. '' becomes None."""
    for space in SPACE_LIKE:
        text = text.replace(space, " ")
    kept = "".join(ch for ch in text if ch in KEEPABLE)
    collapsed = re.sub(r"\s+", " ", kept).strip()
    return collapsed or None


def as_number(text: str | None) -> int | None:
    """Interpret a cell as an integer, or None.

    None covers three different situations that the raw layer keeps apart by
    storing the text: an empty cell, a dash, and '**' -- which the PDF defines
    as « Nombre de transactions insuffisant pour produire une statistique
    fiable », a figure APCIQ withheld rather than one that does not exist.
    """
    if text is None:
        return None
    digits = re.sub(r"[^0-9-]", "", text)
    return int(digits) if re.fullmatch(r"-?\d+", digits) else None


def _joined(chars) -> str:
    return "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"]))


# --- page structure ----------------------------------------------------------


def title_of(page) -> str:
    """The page heading, read left to right.

    Sorted by x alone rather than by (y, x): in the 2026 edition the ligature
    of "L'Île-des-Sœurs" sits a fraction of a point higher than its
    neighbours, and sorting by y first hoisted the "œ" to the front of the
    string -- which silently cost one of the eighteen sectors.
    """
    h, w = page.height, page.width
    chars = [
        c for c in page.chars
        if c["top"] / h < TITLE_MAX_Y and c["x0"] / w < TITLE_MAX_X
    ]
    return _joined(chars).strip()


def area_of(title: str) -> str | None:
    """'island', 'sector-NN' for the 18 island sectors, or None to skip.

    None covers the metro summary, Laval, the two shores and the front matter.
    Sectors 19 and above are off the island and out of scope.
    """
    if ISLAND_LABEL in title:
        return ISLAND_AREA_CODE
    match = SECTOR_RE.search(title)
    if not match:
        return None
    number = int(match.group(1))
    return f"sector-{number:02d}" if 1 <= number <= SECTOR_COUNT else None


def _table2_chars(page) -> list[dict]:
    return [
        c for c in page.chars
        if c["x0"] / page.width >= TABLE2_MIN_X
        and TABLE2_MIN_Y <= c["top"] / page.height <= TABLE2_MAX_Y
    ]


def _lines(chars, height: float) -> list[tuple[float, list[dict]]]:
    """Characters grouped into typeset lines, on their exact shared top."""
    ordered = sorted(chars, key=lambda c: (c["top"], c["x0"]))
    lines: list[tuple[float, list[dict]]] = []
    current: list[dict] = []
    anchor = 0.0
    for char in ordered:
        y = char["top"] / height
        if not current or abs(y - anchor) > LABEL_LINE_TOLERANCE:
            if current:
                lines.append((anchor, current))
            anchor, current = y, []
        current.append(char)
    if current:
        lines.append((anchor, current))
    return lines


def _label_right_edge(metric_lines, width: float) -> float:
    """Where the row labels stop on this page.

    Needed because the label area is not always only letters. The 2019 Q3
    edition prints a lone currency sign at 0.414 on every price row -- part of
    the label, not a cell -- and counting it as one turned six-cell rows into
    seven-run rows, leaving the page with nothing to calibrate on.

    Taken over ALL the page's labels, so the longest one sets the boundary for
    every row -- and capped, because a label line sometimes shares its typeset
    top with text from the neighbouring tables further right. Without the cap,
    one stray word at 0.95 swallows the whole row.
    """
    edges = [c["x1"] / width
             for _, _, line in metric_lines
             for c in line
             if c["text"].isalpha() and c["x1"] / width <= LABEL_MAX_X]
    return max(edges) if edges else TABLE2_MIN_X


def _runs_of(row_chars, width: float, left_bound: float) -> tuple[Run, ...]:
    """Split a row's cell characters into cells.

    Only characters a cell can contain survive: that removes the letters of
    the row label and the trend arrows in one step, without needing to know
    where the label ends or which glyph an arrow is in this edition.

    The split threshold is twice the median character width of this row, not
    a fixed fraction of the page. Inside a cell, the widest gap is the
    non-breaking space between thousands, under one character width. Between
    cells the gap is ten or more. The margin holds on every archived edition
    and on both page sizes.
    """
    cells = [(c["x0"] / width, c["x1"] / width, clean_cell(c["text"]))
             for c in sorted(row_chars, key=lambda c: c["x0"])]
    cells = [(x0, x1, text) for x0, x1, text in cells if text and x0 > left_bound]
    if not cells:
        return ()

    char_width = statistics.median(x1 - x0 for x0, x1, _ in cells)
    threshold = RUN_GAP_IN_CHAR_WIDTHS * char_width

    runs: list[list] = []
    for x0, x1, text in cells:
        if runs and x0 - runs[-1][1] <= threshold:
            # Put the space back. The splitter works on inked characters only,
            # so the space between thousands is not in `cells` -- but it is in
            # the figure, and the raw layer stores a price exactly as printed.
            separator = " " if x0 - runs[-1][1] > char_width / 2 else ""
            runs[-1][1] = max(runs[-1][1], x1)
            runs[-1][2] += separator + text
        else:
            runs.append([x0, x1, text])
    return tuple(Run(x0, x1, text) for x0, x1, text in runs)


def scan_page(page, page_number: int) -> list[RowScan]:
    """Every data row of one island or sector page, cells not yet attributed."""
    title = title_of(page)
    area = area_of(title)
    if area is None:
        return []

    height, width = page.height, page.width
    chars = _table2_chars(page)

    category_at: list[tuple[float, str, str]] = []
    metric_at: list[tuple[float, str, list[dict]]] = []

    for top, line in _lines(chars, height):
        text = _joined(line)
        heading = next((code for needle, code in CATEGORY_RULES if needle in text), None)
        if heading is not None:
            category_at.append((top, heading, text.strip()))
            continue
        if any(word in text for word in PERIOD_HEADER_WORDS):
            continue
        # The needle is matched against the whole line because in several
        # editions the label and its figures share one typeset line, so the
        # text reads "Ventes24-12416 %". The label alone is cut out below.
        metric = next((code for needle, code in METRIC_RULES if needle in text), None)
        if metric is not None:
            metric_at.append((top, metric, line))

    label_right = _label_right_edge(metric_at, width)

    scans: list[RowScan] = []
    for top, metric, line in metric_at:
        preceding = [c for c in category_at if c[0] < top]
        if not preceding:
            continue                       # a labelled row above the first block
        _, category, category_label = preceding[-1]
        label = _joined([c for c in line if c["x0"] / width < label_right]).strip()
        row_chars = [c for c in chars if abs(c["top"] / height - top) <= ROW_WINDOW]
        scans.append(
            RowScan(
                page_number=page_number,
                area_code=area,
                area_label=title,
                category=category,
                category_label=category_label,
                metric=metric,
                metric_label=label,
                runs=_runs_of(row_chars, width, label_right),
            )
        )
    return scans


# --- calibration -------------------------------------------------------------


def calibrate_columns(scans: list[RowScan], *, where: str = "") -> list[float]:
    """The five column centres of one page, read off that page.

    Two kinds of row vote. A row showing all five cells places all five
    columns. A row showing four places the first four -- and those are the
    common case, because only the two price rows of each category carry a
    five-year change, so eleven of the fifteen rows of a page stop at four.
    Calibrating on the six price rows alone left several pages of the 2019 and
    2021 editions with nothing to calibrate on.

    Run centres are stable to about 0.005 of a page -- a count and a price in
    the same column line up that closely -- while the columns themselves are
    0.06 to 0.10 apart, so the median is a firm anchor rather than an average
    of noise.
    """
    votes5 = [s.runs for s in scans if len(s.runs) == COLUMN_COUNT]
    votes4 = [s.runs for s in scans if len(s.runs) == COLUMN_COUNT - 1]
    voters = len(votes5) + len(votes4)
    if voters < MIN_ROWS_FOR_CALIBRATION:
        raise SourceLayoutError(
            f"{where}: only {voters} rows of {len(scans)} show four or five "
            f"cells, which is not enough to locate the columns (need "
            f"{MIN_ROWS_FOR_CALIBRATION}). The table has been redesigned."
        )

    anchors = [
        statistics.median([runs[i].centre for runs in votes5]
                          + [runs[i].centre for runs in votes4])
        for i in range(COLUMN_COUNT - 1)
    ]
    if votes5:
        anchors.append(statistics.median(runs[-1].centre for runs in votes5))
    else:
        # No row on this page carries a five-year change, so the column has no
        # content to place. Extrapolating keeps the anchor list the right
        # length; nothing will ever be attributed to it.
        anchors.append(2 * anchors[-1] - anchors[-2])

    spacings = [b - a for a, b in zip(anchors, anchors[1:])]
    if min(spacings) <= 0.02:
        raise SourceLayoutError(
            f"{where}: the five columns located at {[round(a, 4) for a in anchors]} "
            f"are not properly separated (smallest spacing {min(spacings):.4f})."
        )
    return anchors


def attribute(runs: tuple[Run, ...], anchors: list[float], *, where: str) -> dict[str, str]:
    """Put each cell of a row in its column, by nearest anchor.

    Attribution rather than cutting: a cell cannot fall between two bands and
    disappear. Two runs landing in the same column are joined -- that is a
    cell the run splitter cut in two, not two cells -- and a run too far from
    every anchor stops the edition.
    """
    spacings = [b - a for a, b in zip(anchors, anchors[1:])]
    tolerance = COLUMN_MATCH_FRACTION * min(spacings)

    cells: dict[str, str] = {}
    for run in runs:
        distances = [abs(run.centre - anchor) for anchor in anchors]
        index = distances.index(min(distances))
        if distances[index] > tolerance:
            raise SourceLayoutError(
                f"{where}: the cell {run.text!r} sits at {run.centre:.4f}, "
                f"{distances[index]:.4f} away from the nearest column "
                f"({anchors[index]:.4f}). The columns of this edition are not "
                f"where its own full rows say they are."
            )
        name = COLUMN_NAMES[index]
        cells[name] = (cells[name] + " " + run.text) if name in cells else run.text
    return cells


EXPECTED_CELLS = {(c, m) for c in CATEGORY_CODES for m in METRIC_CODES}


def parse_pdf(path: Path | str, edition: Edition) -> list[Observation]:
    """Every Tableau 2 observation of the island and its 18 sectors.

    855 rows on a well-formed edition: 19 areas x 3 categories x 5 metrics
    x 3 periods.
    """
    expected_areas = (
        {ISLAND_AREA_CODE} | {f"sector-{n:02d}" for n in range(1, SECTOR_COUNT + 1)}
    )
    scans: list[RowScan] = []
    seen: set[str] = set()

    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            found = scan_page(page, number)
            page.flush_cache()
            if not found:
                continue
            area = found[0].area_code
            if area in seen:
                raise SourceLayoutError(
                    f"{edition}: {area} appears on more than one page "
                    f"(second occurrence on page {number})"
                )
            seen.add(area)
            scans.extend(found)
            if seen == expected_areas:
                # Stop at page 26 instead of 65. Each page of the newer
                # editions carries about 1 470 vector objects for its charts,
                # and pdfminer parses all of them to reach the text: 1.2 s a
                # page. Everything past the island is Laval and the two
                # shores. Safe because the loop only stops once ALL nineteen
                # areas are in hand, never on a count.
                break

    if seen != expected_areas:
        raise SourceLayoutError(
            f"{edition}: expected the island page and {SECTOR_COUNT} sector pages. "
            f"Missing {sorted(expected_areas - seen)}; "
            f"unexpected {sorted(seen - expected_areas)}."
        )

    # Calibrated page by page, not once for the edition: Power BI sizes each
    # table to its own content, so the same edition puts its first column at
    # 0.581 on the island page and 0.542 on the Villeray page.
    anchors_by_page = {
        number: calibrate_columns([s for s in scans if s.page_number == number],
                                  where=f"{edition} page {number}")
        for number in sorted({s.page_number for s in scans})
    }

    observations: list[Observation] = []
    by_area: dict[str, set[tuple[str, str]]] = {}
    for scan in scans:
        where = f"{edition} page {scan.page_number} ({scan.area_code}), row '{scan.metric_label}'"
        cells = attribute(scan.runs, anchors_by_page[scan.page_number], where=where)
        by_area.setdefault(scan.area_code, set()).add((scan.category, scan.metric))
        for period, value_column, change_column in PERIODS:
            observations.append(
                Observation(
                    edition_year=edition.year,
                    edition_quarter=edition.quarter,
                    area_code=scan.area_code,
                    property_category=scan.category,
                    metric_code=scan.metric,
                    period_code=period,
                    value_text=cells.get(value_column) if value_column else None,
                    change_percent_text=cells.get(change_column),
                    source_area_label=scan.area_label,
                    source_category_label=scan.category_label,
                    source_metric_label=scan.metric_label,
                    source_page=scan.page_number,
                )
            )

    for area, found_cells in sorted(by_area.items()):
        missing = EXPECTED_CELLS - found_cells
        if missing:
            raise SourceLayoutError(
                f"{edition}: {area} is missing {len(missing)} of the 15 rows of "
                f"Tableau 2: {sorted(missing)}"
            )
    return observations


# --- control totals ----------------------------------------------------------

# A count cell holds one of three things, and they are not the same thing:
#
#   '12'   a count
#   '-'    nothing to count. L'Île-des-Sœurs has no plex at all, so its plex
#          count rows carry a dash quarter after quarter -- while its price
#          rows carry '**', because a price of nothing cannot be withheld or
#          published, it simply does not exist.
#   '**'   « Nombre de transactions insuffisant pour produire une statistique
#          fiable ». Withheld, not absent.
#
# Reading the dash as zero is an interpretation, so it is one the control
# totals verify rather than assume: with the dash read as zero, the eighteen
# sectors add up to the island page exactly, on every archived quarter. Were
# the dash hiding a real figure, they would not.
NO_COUNT_MARKER = "-"


def count_of(text: str | None, *, what: str) -> int:
    """A count cell as a number, with the dash read as zero. Raises otherwise."""
    if text == NO_COUNT_MARKER:
        return 0
    value = as_number(text)
    if value is None:
        raise SourceLayoutError(
            f"{what}: expected a count, found {text!r}. Either the cell was "
            f"read from the wrong place, or APCIQ started printing counts a "
            f"way this parser has never seen."
        )
    return value


def check_island_totals(observations: list[Observation]) -> dict[str, tuple[int, int]]:
    """The 18 sectors must sum to the island page, category by category.

    The control that makes a positional parser believable. A parser reading
    one column to the left produces numbers that look entirely plausible; it
    does not produce eighteen of them that add up to a nineteenth published
    independently on another page.

    Quarterly sales are the right control: they are counts, APCIQ never
    withholds them for being too few, and unlike active listings -- an average
    of month-end counts -- they are additive by construction.

    Returns {category: (island, sum of sectors)} and raises on any difference.
    """
    island: dict[str, int] = {}
    sectors: dict[str, int] = {}

    for observation in observations:
        if observation.metric_code != "sales" or observation.period_code != "quarter":
            continue
        value = count_of(
            observation.value_text,
            what=f"{observation.area_code}/{observation.property_category} quarterly sales",
        )
        target = island if observation.area_code == ISLAND_AREA_CODE else sectors
        target[observation.property_category] = (
            target.get(observation.property_category, 0) + value
        )

    result = {c: (island.get(c, 0), sectors.get(c, 0)) for c in CATEGORY_CODES}
    off = {c: pair for c, pair in result.items() if pair[0] != pair[1]}
    if off:
        detail = ", ".join(
            f"{c}: island {i}, sectors {s} (difference {s - i:+})"
            for c, (i, s) in off.items()
        )
        raise SourceLayoutError(
            "the 18 sectors do not add up to the island page -- " + detail
        )
    return result


# A second control, on a second row of the table, with a tolerance that is
# derived rather than chosen. Active listings are « la moyenne des données
# mensuelles pour la période visée », rounded to a whole number once per
# sector; the island figure is rounded once for the whole island. Eighteen
# roundings of at most half a unit each cannot drift further than nine.
# Observed drift on the archived editions: 0 to 3.
#
# Loose, but not decorative: a column read one place over would be out by
# hundreds, not by nine.
LISTING_TOTAL_TOLERANCE = 9


def check_listing_totals(observations: list[Observation]) -> dict[tuple[str, str], int]:
    """Same control as check_island_totals, on active listings. Returns drifts."""
    island: dict[tuple[str, str], int] = {}
    sectors: dict[tuple[str, str], int] = {}

    for observation in observations:
        if observation.metric_code != "active_listings" or observation.period_code == "five_year":
            continue
        value = count_of(
            observation.value_text,
            what=f"{observation.area_code}/{observation.property_category} "
                 f"active listings ({observation.period_code})",
        )
        key = (observation.period_code, observation.property_category)
        target = island if observation.area_code == ISLAND_AREA_CODE else sectors
        target[key] = target.get(key, 0) + value

    drift = {key: sectors.get(key, 0) - total for key, total in island.items()}
    off = {k: d for k, d in drift.items() if abs(d) > LISTING_TOTAL_TOLERANCE}
    if off:
        detail = ", ".join(f"{period}/{category}: {d:+}" for (period, category), d in off.items())
        raise SourceLayoutError(
            "active listings of the 18 sectors miss the island page by more "
            f"than rounding can explain (tolerance {LISTING_TOTAL_TOLERANCE}) -- "
            + detail
        )
    return drift
