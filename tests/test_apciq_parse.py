"""Tests for the APCIQ Baromètre parser.

Two families here, on top of the two the rest of the suite already has:

  * pure tests      -- the catalogue, the cell cleaning, the archive checks.
                       No file, no network, no database.
  * PDF tests       -- run against real archived editions. The PDFs are not in
                       git (the licence forbids redistributing them, and they
                       weigh 200 MB), so these skip with an explicit message
                       when the archive is empty rather than failing.

The PDF tests carry values transcribed BY EYE off the rendered pages. That is
the point: a positional parser can only be trusted against something read
independently of it. Two of them are negative controls -- they break the
parser on purpose and check that it refuses rather than returning something
plausible.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingestion.apciq import download, editions, parse
from ingestion.apciq.editions import Edition

ARCHIVE = Path(__file__).resolve().parents[1] / editions.ARCHIVE_DIR

# The three editions used to measure the layout. Chosen apart on purpose:
# 2019 and 2022 use a 1008 x 612 pt page with one text box per glyph, 2026 a
# 3825 x 2340 pt page with whole words.
REFERENCE_EDITIONS = (Edition(2019, 2), Edition(2022, 4), Edition(2026, 2))


def _archived(edition: Edition) -> Path:
    path = ARCHIVE / edition.filename
    if not path.exists():
        pytest.skip(
            f"{path} is not on disk. The PDFs are not versioned; fetch them "
            f"with:  python -m ingestion.apciq.run --dry-run --only "
            f"{edition.year}Q{edition.quarter}"
        )
    return path


# Reading one 2026-format edition costs about 30 seconds: its pages carry
# roughly 1 470 vector objects each for the charts, and pdfminer parses all of
# them to reach the text. Parsed once per session, then shared.
_PARSED: dict[Edition, list[parse.Observation]] = {}


def parsed(edition: Edition) -> list[parse.Observation]:
    path = _archived(edition)
    if edition not in _PARSED:
        _PARSED[edition] = parse.parse_pdf(path, edition)
    return _PARSED[edition]


@pytest.fixture(scope="module")
def observations_2026() -> list[parse.Observation]:
    return parsed(Edition(2026, 2))


def one_page(edition: Edition, page_number: int):
    """A single page, for the tests that only need one. Costs about a second."""
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(_archived(edition)) as pdf:
        page = pdf.pages[page_number - 1]
        page.chars          # force the parse inside the context manager
        return page


def cell(observations, area, category, metric, period):
    """The one observation matching, or a readable failure."""
    hits = [
        o for o in observations
        if o.area_code == area and o.property_category == category
        and o.metric_code == metric and o.period_code == period
    ]
    assert len(hits) == 1, f"{area}/{category}/{metric}/{period}: {len(hits)} rows"
    return hits[0]


# --- the catalogue -----------------------------------------------------------


def test_the_url_follows_the_pattern_that_was_probed():
    edition = Edition(2026, 2)
    assert edition.code == "202602"
    assert edition.filename == "202602-bar-mtl.pdf"
    assert edition.url == "https://com.apciq.ca/sam/pdf/bar/2026/202602-bar-mtl.pdf"


def test_a_quarter_outside_one_to_four_is_refused():
    with pytest.raises(ValueError):
        Edition(2026, 5)


def test_the_archive_starts_at_2019_q2_and_runs_without_a_gap():
    found = editions.candidate_editions(date(2026, 8, 23))
    assert found[0] == Edition(2019, 2)     # 2019 Q1 answers 404
    assert found[-1] == Edition(2026, 3)    # the quarter containing that date
    assert len(found) == 30
    # Consecutive, with no quarter skipped and none repeated.
    as_numbers = [e.year * 4 + e.quarter for e in found]
    assert as_numbers == list(range(as_numbers[0], as_numbers[0] + len(found)))


# --- reading a cell ----------------------------------------------------------


def test_the_thousands_separator_survives_but_the_trend_arrow_does_not():
    # A non-breaking space separates thousands in the source, and the down
    # arrow U+1F847 is a decoration that duplicates the sign of the change.
    assert parse.clean_cell("123 456 $\U0001f847") == "123 456 $"


def test_the_withheld_marker_is_kept_and_an_empty_cell_becomes_none():
    # '**' is defined by the source as « Nombre de transactions insuffisant
    # pour produire une statistique fiable ». It is a statement, not a blank.
    assert parse.clean_cell("**") == "**"
    assert parse.clean_cell("\U0001f845 ") is None


def test_a_withheld_figure_is_not_read_as_a_number():
    assert parse.as_number("123 456 $") == 123456
    assert parse.as_number("-9 %") == -9
    assert parse.as_number("**") is None
    assert parse.as_number("-") is None
    assert parse.as_number(None) is None


# --- reading a page title ----------------------------------------------------


def test_the_island_and_its_eighteen_sectors_are_recognised():
    assert parse.area_of("Île de Montréal") == "island"
    assert parse.area_of("Secteur 1 : Ouest-de-l'Île-Sud") == "sector-01"
    assert parse.area_of("Secteur 18 : Pointe Est de l'Île") == "sector-18"


def test_sectors_off_the_island_are_skipped():
    # 19 and beyond are Laval, the north shore and the south shore. The same
    # PDF carries all 51 metro sectors; only the island is in scope.
    assert parse.area_of("Secteur 19 : Centre-Ville de Laval") is None
    assert parse.area_of("Secteur 51 : Saint-Luc/L'Acadie") is None
    assert parse.area_of("Région métropolitaine de Montréal") is None
    assert parse.area_of("Définition des secteurs") is None


def test_a_title_whose_ligature_is_out_of_order_is_still_read():
    # Regression. Sorting the title characters by vertical position first put
    # the "oe" ligature of L'Île-des-Soeurs ahead of the rest of the string,
    # so the page stopped matching "Secteur 10 :" and one of the eighteen
    # sectors disappeared from the load without any error.
    assert parse.area_of("œSecteur 10 : L'Île-des-Surs") == "sector-10"


# --- the archive checks ------------------------------------------------------


def _entry(edition, present):
    path = Path("x.pdf") if present else None
    return download.ArchiveEntry(edition, path, "cached" if present else "not-published")


def test_a_quarter_missing_at_the_end_is_normal():
    # APCIQ publishes weeks after the quarter closes, so the newest candidates
    # legitimately answer 404.
    entries = [_entry(Edition(2026, q), q < 3) for q in (1, 2, 3, 4)]
    download.check_no_hole(entries)


def test_a_quarter_missing_in_the_middle_stops_everything():
    entries = [_entry(Edition(2026, q), q != 2) for q in (1, 2, 3, 4)]
    with pytest.raises(download.EditionNotPublished, match="gap inside the archive"):
        download.check_no_hole(entries)


# --- against the real PDFs ---------------------------------------------------


@pytest.mark.parametrize("edition", REFERENCE_EDITIONS, ids=str)
def test_an_edition_yields_the_full_grid(edition):
    observations = parsed(edition)
    # 19 areas x 3 categories x 5 metrics x 3 periods.
    assert len(observations) == 855
    assert {o.area_code for o in observations} == (
        {"island"} | {f"sector-{n:02d}" for n in range(1, 19)}
    )


@pytest.mark.parametrize("edition", REFERENCE_EDITIONS, ids=str)
def test_the_eighteen_sectors_add_up_to_the_island_page(edition):
    """The control that makes the whole extraction believable.

    It also settles a question left open by the geography model: whether APCIQ
    sector 4 (Le Sud-Ouest, Verdun) overlaps sector 10 (L'Île-des-Sœurs, part
    of Verdun). If it did, the sectors would over-count the island. They do
    not, on three editions seven years apart -- so sector 4 excludes the
    island, and the two do not overlap.
    """
    observations = parsed(edition)
    totals = parse.check_island_totals(observations)
    for category, (island, sectors) in totals.items():
        assert island == sectors, category
        assert island > 0, category


@pytest.mark.parametrize("edition", REFERENCE_EDITIONS, ids=str)
def test_active_listings_agree_within_what_rounding_allows(edition):
    observations = parsed(edition)
    drift = parse.check_listing_totals(observations)
    assert drift, "no active-listing rows were read at all"
    assert max(abs(d) for d in drift.values()) <= parse.LISTING_TOTAL_TOLERANCE


def test_the_page_size_tripled_and_the_parser_did_not_notice():
    """The reason every coordinate in parse.py is a fraction.

    1008 x 612 pt in 2019, 3825 x 2340 in 2026. A parser holding absolute
    point coordinates from one edition reads nothing on the other.
    """
    sizes = [
        (round(page.width), round(page.height))
        for page in (one_page(Edition(2019, 2), 9), one_page(Edition(2026, 2), 9))
    ]
    assert sizes == [(1008, 612), (3825, 2340)]
    assert sizes[1][0] / sizes[0][0] > 3.5


def test_the_figures_match_what_is_printed_on_the_page(observations_2026):
    """Values transcribed by eye from the 2026 Q2 edition.

    Page 8 (Île de Montréal) and page 9 (Secteur 1). Read off the rendered
    page, not produced by this parser -- otherwise the test would only prove
    the parser agrees with itself.
    """
    single = cell(observations_2026, "island", "single_family", "median_price", "quarter")
    assert (single.value_text, single.change_percent_text) == ("<chiffre retire 2026-08-23 -- licence APCIQ>", "<chiffre retire 2026-08-23 -- licence APCIQ>")

    trailing = cell(observations_2026, "island", "single_family", "median_price", "trailing_12m")
    assert (trailing.value_text, trailing.change_percent_text) == ("<chiffre retire 2026-08-23 -- licence APCIQ>", "<chiffre retire 2026-08-23 -- licence APCIQ>")

    five = cell(observations_2026, "island", "single_family", "median_price", "five_year")
    assert (five.value_text, five.change_percent_text) == (None, "<chiffre retire 2026-08-23 -- licence APCIQ>")

    condo = cell(observations_2026, "island", "condo", "median_price", "quarter")
    assert (condo.value_text, condo.change_percent_text) == ("<chiffre retire 2026-08-23 -- licence APCIQ>", "<chiffre retire 2026-08-23 -- licence APCIQ>")

    days = cell(observations_2026, "island", "single_family", "days_on_market", "trailing_12m")
    assert (days.value_text, days.change_percent_text) == ("<chiffre retire 2026-08-23 -- licence APCIQ>", "<chiffre retire 2026-08-23 -- licence APCIQ>")

    sales = cell(observations_2026, "sector-01", "single_family", "sales", "quarter")
    assert (sales.value_text, sales.change_percent_text) == ("<chiffre retire 2026-08-23 -- licence APCIQ>", "<chiffre retire 2026-08-23 -- licence APCIQ>")


def test_the_source_labels_are_kept_verbatim(observations_2026):
    row = cell(observations_2026, "sector-01", "plex", "median_price", "quarter")
    assert row.source_metric_label == "Prix médian"
    assert row.source_category_label == "Plex (2 à 5 logements)"
    assert row.source_area_label == "Secteur 1 : Ouest-de-l'Île-Sud"
    # And the withheld marker reaches the raw layer as itself.
    assert row.value_text == "**"


def test_a_cell_typeset_below_its_own_label_is_still_captured(observations_2026):
    """Regression on the defect that cost the first version of this parser.

    In this edition the quarter-value cell of some rows sits about 0.003 of a
    page lower than the label of its row. Grouping characters by proximity
    dropped them: the figure vanished, no error was raised, and the island
    control total still balanced because it only looks at sales.
    """
    row = cell(observations_2026, "sector-01", "plex", "active_listings", "quarter")
    assert row.value_text == "11"


# --- negative controls -------------------------------------------------------


def _run(centre, text="1"):
    return parse.Run(centre - 0.005, centre + 0.005, text)


ANCHORS = [0.586, 0.684, 0.762, 0.858, 0.947]


def test_each_cell_lands_in_the_column_nearest_to_it():
    cells = attribute_row([0.586, 0.684, 0.762, 0.858, 0.947], ["12", "3%", "45", "6%", "7%"])
    assert cells == {
        "quarter_value": "12", "quarter_change": "3%",
        "trailing_value": "45", "trailing_change": "6%",
        "five_year_change": "7%",
    }


def test_a_row_missing_its_middle_cells_still_places_the_others():
    """The case that makes order-based reading wrong.

    A thin sector prints a count and its twelve-month count and nothing else.
    Read in order, the second figure would be filed as the quarterly change.
    """
    cells = attribute_row([0.586, 0.762], ["0", "13"])
    assert cells == {"quarter_value": "0", "trailing_value": "13"}


def test_a_cell_far_from_every_column_stops_the_edition():
    with pytest.raises(parse.SourceLayoutError, match="away from the nearest column"):
        # Anchors here are 0.078 apart at the narrowest, so a cell is accepted
        # up to 0.039 from one. 0.635 is 0.049 from the nearest.
        attribute_row([0.635], ["999"])


def test_a_cell_the_splitter_cut_in_two_is_joined_back():
    cells = attribute_row([0.583, 0.590], ["123", "456"])
    assert cells["quarter_value"] == "123 456"


def attribute_row(centres, texts):
    runs = tuple(_run(c, t) for c, t in zip(centres, texts))
    return parse.attribute(runs, ANCHORS, where="test")


def test_a_page_whose_columns_cannot_be_located_is_refused(monkeypatch):
    """Break calibration on purpose; the parser must refuse.

    Raising the floor above what any page can supply is the cheapest way to
    reach the branch. What it proves is the important part: a page the parser
    cannot calibrate stops the edition instead of being read with someone
    else page geometry.
    """
    monkeypatch.setattr(parse, "MIN_ROWS_FOR_CALIBRATION", 99)
    with pytest.raises(parse.SourceLayoutError, match="not enough to locate the columns"):
        parse.parse_pdf(_archived(Edition(2026, 2)), Edition(2026, 2))
