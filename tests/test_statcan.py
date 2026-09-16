"""What the Statistics Canada ingestion must guarantee.

The offline tests run against real extracts of the three published files,
cut down to a few dozen rows and committed as fixtures. Real rows rather than
invented ones, for the reason already recorded in test_boundaries.py: a stub I
write can only contain the shape I already expect. The Statistics Canada Open
Licence permits redistributing them, which is exactly what APCIQ's does not.

The tests worth reading twice are the ones about symbols. Six columns of the
income file are named `Symbol`, and losing their pairing with the measure
beside them would not raise anything -- it would quietly turn "the state knows
this number and may not print it" into "there is no number", and every value
would still look like a plausible income.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from ingestion.statcan import datasets, download, load, parse

FIXTURES = Path(__file__).parent / "fixtures"

GAF = FIXTURES / "statcan_gaf_sample.zip"
INCOME = FIXTURES / "statcan_income_sample.zip"
BOUNDARIES = FIXTURES / "statcan_ct_boundary_sample.zip"


@pytest.fixture(scope="module")
def gaf_bytes() -> bytes:
    return GAF.read_bytes()


@pytest.fixture(scope="module")
def income_bytes() -> bytes:
    return INCOME.read_bytes()


@pytest.fixture(scope="module")
def boundary_bytes() -> bytes:
    return BOUNDARIES.read_bytes()


# ---------------------------------------------------------------------------
# The Geographic Attribute File. No network, no database.
# ---------------------------------------------------------------------------


def test_only_island_blocks_are_kept(gaf_bytes):
    """The fixture holds Laval blocks too, and Laval is not the Island.

    Laval sits inside the same census metropolitan area, which is precisely
    why the perimeter is a census division and not a CMA.
    """
    blocks = parse.island_blocks(gaf_bytes)

    assert blocks, "no block survived the filter"
    assert all(b.csd_uid.startswith("2466") for b in blocks)

    with zipfile.ZipFile(io.BytesIO(gaf_bytes)) as archive:
        with archive.open("2021_92-151_X.csv") as handle:
            total = sum(1 for _ in csv.DictReader(
                io.TextIOWrapper(handle, encoding="latin-1", newline="")))
    assert len(blocks) < total, "the filter kept everything, so it filtered nothing"


def test_every_block_carries_its_municipality_and_its_tract(gaf_bytes):
    """This is the pairing that replaced the spatial join."""
    for block in parse.island_blocks(gaf_bytes):
        assert block.db_uid
        assert block.csd_uid.startswith(datasets.ISLAND_CD_UID)
        assert block.ct_uid, f"block {block.db_uid} has no census tract"
        assert block.ct_dguid.endswith(block.ct_uid)


def test_the_municipal_code_is_the_census_code_without_its_province(gaf_bytes):
    """csd_uid = '24' + MAMH code. Checked, because the whole join rests on it."""
    for block in parse.island_blocks(gaf_bytes):
        assert block.csd_uid[:2] == "24"
        assert len(block.csd_uid[2:]) == 5


def test_the_representative_point_is_published_in_both_systems(gaf_bytes):
    """Both coordinate pairs must be present: one proves the other's CRS."""
    for block in parse.island_blocks(gaf_bytes):
        assert block.da_lambert_x and block.da_lambert_y
        assert block.da_latitude and block.da_longitude
        assert 45.0 < float(block.da_latitude) < 46.0
        assert -74.5 < float(block.da_longitude) < -73.0


# ---------------------------------------------------------------------------
# The income table
# ---------------------------------------------------------------------------


def test_only_the_montreal_metropolitan_area_is_kept(income_bytes):
    """The fixture carries a tract from another CMA, and it must not survive."""
    rows = parse.cma_income_rows(income_bytes)

    assert rows
    assert all(
        row.dguid.startswith(datasets.CT_DGUID_PREFIX) or row.dguid == datasets.CMA_DGUID
        for row in rows
    )
    assert not any(row.dguid.startswith("2021S05079320") for row in rows)


def test_the_cube_carries_seventy_seven_rows_per_geography(income_bytes):
    rows = parse.cma_income_rows(income_bytes)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.dguid] = counts.get(row.dguid, 0) + 1
    assert set(counts.values()) == {parse.ROWS_PER_GEOGRAPHY}


def test_blank_rows_do_not_stop_the_parse(income_bytes):
    """The published file contains empty lines. A strict positional parser
    raises IndexError partway through -- the trap recorded in
    docs/data-sources.md section 2.4, whose actual shape was only measured on
    2026-08-24. The fixture keeps two of them."""
    with zipfile.ZipFile(io.BytesIO(income_bytes)) as archive:
        raw = archive.read("98100058.csv").decode("utf-8-sig")
    assert "\n\n" in raw, "the fixture no longer contains the blank rows it is here to test"

    rows = parse.cma_income_rows(income_bytes)
    assert rows


def test_each_measure_keeps_its_own_symbol(income_bytes):
    """The pairing between a value and the symbol printed beside it.

    Losing it is the failure mode this module exists to prevent, and it has no
    symptom: the numbers stay plausible.
    """
    rows = parse.cma_income_rows(income_bytes)

    for row in rows:
        assert set(row.values) == set(row.symbols)
        for key in row.values:
            symbol = row.symbols[key]
            assert symbol in datasets.SYMBOL_MEANINGS, f"unknown symbol {symbol!r}"

    seen = {s for row in rows for s in row.symbols.values()}
    assert seen != {""}, "the fixture contains no suppressed cell, so it proves nothing"


def test_a_cell_that_is_not_applicable_carries_a_literal_zero(income_bytes):
    """The nastiest thing in this file, and it is measured, not supposed.

    The source uses TWO different placeholders for its two kinds of non-value,
    and one of them is a digit. Counted over the whole Montréal metropolitan
    area on 2026-08-24, for the four income measures:

        symbol ''     -> a real number, never zero
        symbol '...'  -> the literal '0'     18 404 cells per 2020 measure
        symbol 'x'    -> empty                9 340 cells per 2020 measure

    So a parser that reads the value column and ignores the symbol beside it
    does not get NULLs it might notice. It gets tens of thousands of median
    household incomes of zero dollars, which average into every aggregate
    downstream without ever looking wrong enough to investigate.

    AND THE ZERO CANNOT BE FILTERED OUT ON SIGHT

    Household COUNTS behave differently: 19 385 of them are published as a
    genuine zero, because a tract really can contain no household of a given
    size and type. So "drop the zeros" would be wrong for counts and right for
    incomes, and only the symbol column tells the two apart.

    This is why the raw layer keeps both columns and why the conversion to a
    number lives in a dbt macro that fires on the symbol, never on the value
    looking empty.
    """
    rows = parse.cma_income_rows(income_bytes)

    income_measures = {
        "median_total_income_2020", "median_total_income_2015",
        "median_aftertax_income_2020", "median_aftertax_income_2015",
    }
    count_measures = {"households_2021", "households_2016"}

    by_symbol: dict[str, set[str]] = {}
    published_counts: set[str] = set()
    for row in rows:
        for key, value in row.values.items():
            kind = "empty" if value == "" else ("zero" if value == "0" else "number")
            if key in income_measures:
                by_symbol.setdefault(row.symbols[key], set()).add(kind)
            elif key in count_measures and row.symbols[key] == "":
                published_counts.add(kind)

    assert by_symbol.get("...") == {"zero"}, (
        "'not applicable' no longer prints a literal zero on an income -- "
        "re-measure before changing anything downstream"
    )
    assert by_symbol.get("x") == {"empty"}
    assert by_symbol.get("") == {"number"}, (
        "a published income is zero, which has never happened -- the value and "
        "symbol columns may have drifted apart"
    )

    # The other half of the trap: a published count of zero is real data.
    assert "zero" in published_counts, (
        "the fixture holds no published zero count, so it cannot show why "
        "zeros must not be filtered out wholesale"
    )


def test_a_dictionary_reader_would_lose_five_symbol_columns(income_bytes):
    """Why the file is read positionally, demonstrated rather than asserted.

    csv.DictReader keeps the last column of a repeated name. Six measures ship
    six columns called `Symbol`, so five of the six meanings disappear -- and
    every value column still reads fine, which is what makes it dangerous.
    """
    with zipfile.ZipFile(io.BytesIO(income_bytes)) as archive:
        with archive.open("98100058.csv") as handle:
            reader = csv.DictReader(
                io.TextIOWrapper(handle, encoding="utf-8-sig", newline=""))
            header = reader.fieldnames or []
            first = next(iter(reader))

    assert header.count("Symbol") == 6
    assert len([k for k in first if k == "Symbol"]) == 1


def test_a_reordered_file_is_refused(income_bytes):
    """Moving a symbol column away from its measure must fail loudly."""
    with zipfile.ZipFile(io.BytesIO(income_bytes)) as archive:
        rows = list(csv.reader(io.StringIO(
            archive.read("98100058.csv").decode("utf-8-sig"))))

    rows[0][7] = "Something Else"          # the symbol of the first measure
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)

    damaged = io.BytesIO()
    with zipfile.ZipFile(damaged, "w") as archive:
        archive.writestr("98100058.csv", buffer.getvalue().encode("utf-8"))

    with pytest.raises(parse.ParseError, match="Symbol"):
        parse.cma_income_rows(damaged.getvalue())


def test_a_measure_in_the_last_column_is_refused_with_a_diagnosis():
    """The guard must explain itself, not crash while building its message.

    Found by code review on 2026-09-15: the refusal read header[symbol_index]
    inside its own f-string, so a truncated header raised IndexError instead
    of the ParseError that says what went wrong.
    """
    header = []
    for _, fragment in parse.MEASURES:
        header += [fragment, "Symbol"]
    header.pop()                            # the last measure loses its symbol

    with pytest.raises(parse.ParseError, match="last column"):
        parse._locate_measure_columns(header)


def test_a_renamed_measure_is_refused(income_bytes):
    with zipfile.ZipFile(io.BytesIO(income_bytes)) as archive:
        rows = list(csv.reader(io.StringIO(
            archive.read("98100058.csv").decode("utf-8-sig"))))

    rows[0][10] = "Median household total income (2019)"
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)

    damaged = io.BytesIO()
    with zipfile.ZipFile(damaged, "w") as archive:
        archive.writestr("98100058.csv", buffer.getvalue().encode("utf-8"))

    with pytest.raises(parse.ParseError, match="exactly one column"):
        parse.cma_income_rows(damaged.getvalue())


# ---------------------------------------------------------------------------
# The boundary file
# ---------------------------------------------------------------------------


def test_polygons_become_well_known_text(boundary_bytes, gaf_bytes):
    wanted = {b.ct_uid for b in parse.island_blocks(gaf_bytes)}
    records = parse.tract_boundaries(boundary_bytes, wanted)

    assert {r.ct_uid for r in records} == wanted
    for record in records:
        assert record.geometry_wkt.startswith(("POLYGON(", "MULTIPOLYGON("))
        assert record.geometry_wkt.count("(") == record.geometry_wkt.count(")")
        assert float(record.land_area_km2) > 0


def test_a_tract_with_no_polygon_is_refused(boundary_bytes):
    """Two files from different releases must not merge quietly."""
    with pytest.raises(parse.ParseError, match="no polygon"):
        parse.tract_boundaries(boundary_bytes, {"9999999.99"})


# ---------------------------------------------------------------------------
# Fetching. No network: the session is a stand-in.
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, status_code=200, headers=None, content=b"", payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, *, redirect_to=None, status_code=302, content=b"zip"):
        self._redirect_to = redirect_to
        self._status_code = status_code
        self._content = content
        self.fetched: list[str] = []

    def post(self, url, data=None, allow_redirects=True, timeout=None):
        location = ""
        if self._redirect_to:
            location = f"/census-recensement/alternative.cfm?loc={self._redirect_to}"
        return _Response(status_code=self._status_code, headers={"Location": location})

    def get(self, url, timeout=None):
        self.fetched.append(url)
        return _Response(content=self._content)


def test_the_file_path_comes_from_the_server(monkeypatch):
    """It is read out of the redirect, never written down here."""
    session = _Session(redirect_to="/a/b/files-fichiers/lct_000b21a_e.zip")

    payload, url = download.fetch(datasets.CENSUS_TRACT_BOUNDARIES, session=session)

    assert url.endswith("/files-fichiers/lct_000b21a_e.zip")
    assert payload == b"zip"
    assert session.fetched == [url]


def test_a_file_with_the_wrong_name_is_refused():
    """A boundary file for another geography answers 200 and parses cleanly.

    Nothing downstream would notice: the rows land, the polygons are valid,
    and the map is simply of somewhere else. This is the only cheap moment to
    catch it.
    """
    session = _Session(redirect_to="/a/b/files-fichiers/lcsd000b21a_e.zip")

    with pytest.raises(download.DownloadError, match="does not look like"):
        download.fetch(datasets.CENSUS_TRACT_BOUNDARIES, session=session)


def test_a_form_that_stops_redirecting_is_refused():
    session = _Session(status_code=200)

    with pytest.raises(download.DownloadError, match="instead of a redirect"):
        download.fetch(datasets.CENSUS_TRACT_BOUNDARIES, session=session)


# ---------------------------------------------------------------------------
# Against the real database. Every one of these rolls back.
# ---------------------------------------------------------------------------


@pytest.mark.db
def test_reloading_unchanged_blocks_rewrites_nothing(db_connection, gaf_bytes):
    """Idempotence, proven against the real table rather than asserted.

    The fixture blocks are already in the database from the real run, with the
    same values, so a second load must report nothing at all.
    """
    blocks = parse.island_blocks(gaf_bytes)
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT source_file FROM raw.statcan_geographic_attribute "
            "WHERE db_uid = %s",
            (blocks[0].db_uid,),
        )
        row = cur.fetchone()
    if row is None:
        pytest.skip("the attribute file has not been loaded on this database yet")

    result = load.load_blocks(db_connection, blocks, source_file=row[0])

    assert (result.inserted, result.updated) == (0, 0)


@pytest.mark.db
def test_a_changed_value_is_updated_exactly_once(db_connection, gaf_bytes):
    """The other half of idempotence: a real change must be picked up."""
    blocks = parse.island_blocks(gaf_bytes)
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT source_file FROM raw.statcan_geographic_attribute "
            "WHERE db_uid = %s",
            (blocks[0].db_uid,),
        )
        row = cur.fetchone()
    if row is None:
        pytest.skip("the attribute file has not been loaded on this database yet")

    changed = [
        parse.BlockRecord(**{**block.__dict__, "population_2021": "999999"})
        if block is blocks[0] else block
        for block in blocks
    ]

    result = load.load_blocks(db_connection, changed, source_file=row[0])

    assert (result.inserted, result.updated) == (0, 1)


@pytest.mark.db
def test_the_island_is_sixteen_municipalities(db_connection):
    """Census division 2466 is the Island, exactly. The fact the whole
    perimeter rests on, checked against the loaded table rather than a note."""
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT count(DISTINCT csd_uid) FROM raw.statcan_geographic_attribute"
        )
        (municipalities,) = cur.fetchone()
    if municipalities == 0:
        pytest.skip("the attribute file has not been loaded on this database yet")

    assert municipalities == datasets.ISLAND_MUNICIPALITY_COUNT


@pytest.mark.db
def test_no_census_tract_straddles_a_municipality(db_connection):
    """The measurement that removed a spatial join, as a standing check.

    dbt asserts the same thing on the staging model; this asserts it on the
    raw rows, so it holds even for someone who never runs dbt.
    """
    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT ct_uid, count(DISTINCT csd_uid) AS municipalities
              FROM raw.statcan_geographic_attribute
             WHERE ct_uid <> ''
             GROUP BY ct_uid
            HAVING count(DISTINCT csd_uid) > 1
            """
        )
        straddling = cur.fetchall()
    assert straddling == []


@pytest.mark.db
def test_the_declared_projection_is_the_right_one(db_connection):
    """EPSG:3347 proven, not recognised by its name.

    The attribute file publishes the same representative point twice: in
    Statistics Canada Lambert, and in latitude and longitude. Reprojecting the
    first through the SRID the boundary rows declare must land on the second.

    This project has already loaded a NAD83 lookalike once. It raised nothing
    and made every spatial join return empty.
    """
    with db_connection.cursor() as cur:
        cur.execute("SELECT DISTINCT source_srid FROM raw.statcan_census_tract_boundary")
        srids = [row[0] for row in cur.fetchall()]
        if not srids:
            pytest.skip("the boundary file has not been loaded on this database yet")
        assert srids == [datasets.BOUNDARY_SRID]

        cur.execute(
            """
            SELECT max(ST_Distance(
                       ST_Transform(ST_SetSRID(ST_Point(da_lambert_x::float,
                                                        da_lambert_y::float), %s), 4326)::geography,
                       ST_SetSRID(ST_Point(da_longitude::float,
                                           da_latitude::float), 4326)::geography))
              FROM raw.statcan_geographic_attribute
             WHERE da_lambert_x <> ''
            """,
            (datasets.BOUNDARY_SRID,),
        )
        (worst_metres,) = cur.fetchone()

    assert worst_metres is not None
    assert worst_metres < 5, (
        f"the two published coordinate systems disagree by {worst_metres:.1f} m. "
        f"EPSG:{datasets.BOUNDARY_SRID} is not the projection of this file."
    )
