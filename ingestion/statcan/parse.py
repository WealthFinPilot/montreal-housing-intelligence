"""Turn the downloaded archives into records. No HTTP, no database.

Everything is read straight out of the zip archive in memory. The attribute
file is 298 MB unzipped and never exists as a file on disk: it is streamed,
row by row, and only the 13 844 Island blocks are kept. Same approach as the
MAMH roll, and the same reason -- see ingestion/mamh_roll/extract_roll.py.

THREE TRAPS THIS MODULE PAYS FOR, ALL THREE MEASURED
----------------------------------------------------
1. The income file has SIX columns literally named `Symbol`. Reading it with
   csv.DictReader keeps one of them and silently discards five, which would
   erase exactly the distinction between "suppressed by law" and "value
   published". It is therefore read positionally, and each measure column is
   located by name so a reordering cannot go unnoticed.

2. That same file contains rows of length zero -- two of them, measured. A
   strict positional parser raises IndexError partway through, which is the
   trap docs/data-sources.md section 2.4 recorded without knowing its shape.
   They are empty lines, not truncated records, and they are skipped.

3. Statistics Canada does not leave a cell blank when it has nothing to give.
   It prints `x` (suppressed under the Statistics Act) or `...` (not
   applicable), and those are different claims. Both are carried through
   verbatim beside the value.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass

import shapefile

from ingestion.statcan import datasets


class ParseError(RuntimeError):
    """The archive is not shaped the way this parser was written for."""


# --------------------------------------------------------------------------
# 1. Geographic Attribute File
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockRecord:
    """One dissemination block, with every coarser code it belongs to."""

    db_uid: str
    db_dguid: str
    da_uid: str
    ct_uid: str
    ct_dguid: str
    ct_name: str
    cma_uid: str
    cma_name: str
    csd_uid: str
    csd_name: str
    csd_type: str
    cd_uid: str
    pr_uid: str
    population_2021: str
    total_dwellings_2021: str
    usual_resident_dwellings_2021: str
    land_area_km2: str
    da_lambert_x: str
    da_lambert_y: str
    da_latitude: str
    da_longitude: str


def island_blocks(payload: bytes) -> list[BlockRecord]:
    """Every dissemination block of census division 2466, i.e. the Island.

    The filter is a published code, not a geometry and not a name. Census
    division 2466 was measured to be exactly the 16 Island municipalities on
    2026-08-24 -- docs/data-sources.md section 2.9.
    """
    archive = zipfile.ZipFile(io.BytesIO(payload))
    name = _single_member(archive, ".csv")

    records: list[BlockRecord] = []
    with archive.open(name) as handle:
        # latin-1: the file is not UTF-8, and guessing wrong here corrupts
        # French municipality names rather than raising.
        reader = csv.DictReader(io.TextIOWrapper(handle, encoding="latin-1", newline=""))
        for row in reader:
            csd_uid = (row.get("CSDUID_SDRIDU") or "").strip()
            if not csd_uid.startswith(datasets.ISLAND_CD_UID):
                continue
            records.append(
                BlockRecord(
                    db_uid=row["DBUID_IDIDU"].strip(),
                    db_dguid=row["DBDGUID_IDIDUGD"].strip(),
                    da_uid=row["DAUID_ADIDU"].strip(),
                    ct_uid=row["CTUID_SRIDU"].strip(),
                    ct_dguid=row["CTDGUID_SRIDUGD"].strip(),
                    ct_name=row["CTNAME_SRNOM"].strip(),
                    cma_uid=row["CMAUID_RMRIDU"].strip(),
                    cma_name=row["CMANAME_RMRNOM"].strip(),
                    csd_uid=csd_uid,
                    csd_name=row["CSDNAME_SDRNOM"].strip(),
                    csd_type=row["CSDTYPE_SDRGENRE"].strip(),
                    cd_uid=row["CDUID_DRIDU"].strip(),
                    pr_uid=row["PRUID_PRIDU"].strip(),
                    population_2021=row["DBPOP2021_IDPOP2021"].strip(),
                    total_dwellings_2021=row["DBTDWELL2021_IDTLOG2021"].strip(),
                    usual_resident_dwellings_2021=row["DBURDWELL2021_IDRHLOG2021"].strip(),
                    land_area_km2=row["DBAREA2021_IDSUP2021"].strip(),
                    da_lambert_x=row["DARPLAMX_ADLAMX"].strip(),
                    da_lambert_y=row["DARPLAMY_ADLAMY"].strip(),
                    da_latitude=row["DARPLAT_ADLAT"].strip(),
                    da_longitude=row["DARPLONG_ADLONG"].strip(),
                )
            )

    if not records:
        raise ParseError(
            "no block of census division "
            f"{datasets.ISLAND_CD_UID} was found. The file changed shape, or "
            "the census division codes were renumbered."
        )
    return records


# --------------------------------------------------------------------------
# 2. Household income statistics, table 98100058
# --------------------------------------------------------------------------

# Each measure is followed immediately by its own `Symbol` column. Located by
# a fragment of the published header rather than by position, so a reordered
# file fails here instead of loading six columns into the wrong six fields.
MEASURES: tuple[tuple[str, str], ...] = (
    ("households_2021", "Number of households (2021)"),
    ("households_2016", "Number of households (2016)"),
    ("median_total_income_2020", "Median household total income (2020)"),
    ("median_total_income_2015", "Median household total income (2015)"),
    ("median_aftertax_income_2020", "Median household after-tax income (2020)"),
    ("median_aftertax_income_2015", "Median household after-tax income (2015)"),
)

ROWS_PER_GEOGRAPHY = 77  # 7 household sizes x 11 household types


@dataclass(frozen=True)
class IncomeRecord:
    """One cell of the published cube: a geography, a size, a type."""

    dguid: str
    geo_name: str
    ref_date: str
    household_size: str
    household_type: str
    coordinate: str
    values: dict[str, str]    # measure -> value as printed
    symbols: dict[str, str]   # measure -> symbol as printed


def cma_income_rows(payload: bytes) -> list[IncomeRecord]:
    """Every row of table 98100058 for the Montréal census metropolitan area."""
    archive = zipfile.ZipFile(io.BytesIO(payload))
    name = _single_member(archive, ".csv", exclude="MetaData")

    records: list[IncomeRecord] = []
    blank_rows = 0
    with archive.open(name) as handle:
        reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig", newline=""))
        header = next(reader)
        columns = _locate_measure_columns(header)
        width = len(header)

        for row in reader:
            if not row:
                # Trap 2. Two of these exist in the file, measured.
                blank_rows += 1
                continue
            if len(row) != width:
                raise ParseError(
                    f"a row of {len(row)} fields appeared where {width} were "
                    "expected. Short rows were known to exist as empty lines "
                    "only -- this is something else, and reading it "
                    "positionally would put values in the wrong columns."
                )

            dguid = row[2].strip()
            if not _in_montreal_cma(dguid):
                continue

            records.append(
                IncomeRecord(
                    dguid=dguid,
                    geo_name=row[1].strip(),
                    ref_date=row[0].strip(),
                    household_size=row[3].strip(),
                    household_type=row[4].strip(),
                    coordinate=row[5].strip(),
                    values={key: row[i].strip() for key, (i, _) in columns.items()},
                    symbols={key: row[j].strip() for key, (_, j) in columns.items()},
                )
            )

    if not records:
        raise ParseError(
            f"no row for census metropolitan area {datasets.MONTREAL_CMA_UID} "
            "was found. Check the DGUID prefixes before assuming the table is "
            "empty."
        )
    return records


def _in_montreal_cma(dguid: str) -> bool:
    return dguid == datasets.CMA_DGUID or dguid.startswith(datasets.CT_DGUID_PREFIX)


def _locate_measure_columns(header: list[str]) -> dict[str, tuple[int, int]]:
    """Map each measure to (value column, symbol column).

    Trap 1 lives here. The six symbol columns share one name, so the header
    cannot be turned into a dictionary; the pairing is positional and it is
    checked rather than trusted.
    """
    located: dict[str, tuple[int, int]] = {}
    for key, fragment in MEASURES:
        matches = [i for i, name in enumerate(header) if fragment in name]
        if len(matches) != 1:
            raise ParseError(
                f"expected exactly one column containing {fragment!r}, found "
                f"{len(matches)}. The published table changed shape."
            )
        value_index = matches[0]
        symbol_index = value_index + 1
        if symbol_index >= len(header) or header[symbol_index].strip() != "Symbol":
            raise ParseError(
                f"the column after {fragment!r} is "
                f"{header[symbol_index].strip()!r}, not 'Symbol'. Every measure "
                "is supposed to carry its own symbol column, and losing that "
                "pairing would erase the difference between a suppressed "
                "value and a published one."
            )
        located[key] = (value_index, symbol_index)
    return located


# --------------------------------------------------------------------------
# 3. Census tract boundaries
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundaryRecord:
    ct_uid: str
    dguid: str
    ct_name: str
    pr_uid: str
    land_area_km2: str
    geometry_wkt: str


def tract_boundaries(payload: bytes, ct_uids: set[str]) -> list[BoundaryRecord]:
    """The polygons of the requested census tracts, as well-known text.

    The perimeter is passed in rather than derived here: it comes from the
    attribute table, which is the file that actually knows which tracts are on
    the Island. Deriving it from the geometry would be re-introducing the
    spatial join that section 2.9 established is not needed.
    """
    archive = zipfile.ZipFile(io.BytesIO(payload))
    base = _single_member(archive, ".shp").rsplit(".", 1)[0]

    reader = shapefile.Reader(
        shp=io.BytesIO(archive.read(base + ".shp")),
        dbf=io.BytesIO(archive.read(base + ".dbf")),
        shx=io.BytesIO(archive.read(base + ".shx")),
    )

    records: list[BoundaryRecord] = []
    for item in reader.iterShapeRecords():
        attributes = item.record.as_dict()
        ct_uid = str(attributes.get("CTUID", "")).strip()
        if ct_uid not in ct_uids:
            continue
        records.append(
            BoundaryRecord(
                ct_uid=ct_uid,
                dguid=str(attributes.get("DGUID", "")).strip(),
                ct_name=str(attributes.get("CTNAME", "")).strip(),
                pr_uid=str(attributes.get("PRUID", "")).strip(),
                land_area_km2=str(attributes.get("LANDAREA", "")).strip(),
                geometry_wkt=_to_wkt(item.shape.__geo_interface__),
            )
        )

    missing = ct_uids - {record.ct_uid for record in records}
    if missing:
        raise ParseError(
            f"{len(missing)} census tract(s) present in the attribute file have "
            f"no polygon in the boundary file, for example {sorted(missing)[:5]}. "
            "The two files are from different releases."
        )
    return records


def _to_wkt(geometry: dict) -> str:
    """GeoJSON mapping to well-known text, coordinates untouched.

    Kept in Python rather than done in SQL so the raw layer stores one plain
    serialisation of what the file contained, with no projection and no
    correction applied. Ring order and hole nesting are already resolved by
    the shapefile reader.
    """

    def ring(points) -> str:
        return "(" + ", ".join(f"{x!r} {y!r}" for x, y, *_ in points) + ")"

    def polygon(rings) -> str:
        return "(" + ", ".join(ring(r) for r in rings) + ")"

    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        return "POLYGON(" + ", ".join(ring(r) for r in coordinates) + ")"
    if kind == "MultiPolygon":
        return "MULTIPOLYGON(" + ", ".join(polygon(p) for p in coordinates) + ")"
    raise ParseError(f"unexpected geometry type {kind!r} in the boundary file")


# --------------------------------------------------------------------------


def _single_member(archive: zipfile.ZipFile, suffix: str, *, exclude: str | None = None) -> str:
    """The one member with this suffix. Refuses to pick when there are several."""
    names = [
        name
        for name in archive.namelist()
        if name.lower().endswith(suffix) and (exclude is None or exclude not in name)
    ]
    if len(names) != 1:
        raise ParseError(
            f"expected exactly one {suffix} member in the archive, found "
            f"{len(names)}: {names}. Refusing to guess which one is meant."
        )
    return names[0]


# ---------------------------------------------------------------------------
# The Consumer Price Index series
# ---------------------------------------------------------------------------
#
# Unlike the three files above, nothing is unzipped here: the API already
# returned structured points. What is left to do is the same thing the other
# parsers do -- turn the source's own representation into text, keeping every
# assertion the source made, and deciding nothing.


@dataclass(frozen=True)
class CpiRecord:
    """One monthly index value, with every code the source attached to it."""

    vector_id: str
    ref_period: str
    product_id: str
    coordinate: str
    geo_name: str
    product_name: str
    value: str
    decimals: str
    status_code: str
    symbol_code: str
    scalar_factor_code: str
    security_level_code: str
    frequency_code: str
    uom_code: str
    uom: str
    release_time: str


def _index_value(point: dict) -> str:
    """The index as text, at the precision the source says it publishes.

    A JSON number has no precision of its own -- 169.9 and 169.90 arrive
    identical -- but the point carries `decimals`, which is the source stating
    how many digits it publishes. Formatting to that is therefore closer to
    what was published than repr() would be.

    A null value stays empty rather than becoming a zero. That distinction is
    the whole reason the raw layer stores text: this project has already been
    bitten twice by a non-value that looked like a number, by '...' in J3.3
    and by '-' in J3.2.
    """
    value = point.get("value")
    if value is None:
        return ""
    decimals = point.get("decimals")
    if isinstance(decimals, int) and decimals >= 0:
        return f"{value:.{decimals}f}"
    return repr(value)


def cpi_observations(response, dataset) -> list[CpiRecord]:
    """Turn one SeriesResponse into records. Filters nothing, judges nothing."""
    records: list[CpiRecord] = []
    for point in response.points:
        ref_period = str(point.get("refPer") or "")
        if not ref_period:
            raise ParseError(
                "a data point carries no reference period, so it cannot be "
                "keyed. The response shape has changed."
            )
        records.append(
            CpiRecord(
                vector_id=response.vector_id,
                ref_period=ref_period,
                product_id=str(dataset.product_id),
                coordinate=dataset.coordinate,
                geo_name=dataset.geo_name,
                product_name=dataset.product_name,
                value=_index_value(point),
                decimals=str(point.get("decimals", "")),
                status_code=str(point.get("statusCode", "")),
                symbol_code=str(point.get("symbolCode", "")),
                scalar_factor_code=str(point.get("scalarFactorCode", "")),
                security_level_code=str(point.get("securityLevelCode", "")),
                frequency_code=str(point.get("frequencyCode", "")),
                uom_code=response.uom_code,
                uom=response.uom,
                release_time=str(point.get("releaseTime", "")),
            )
        )
    return records
