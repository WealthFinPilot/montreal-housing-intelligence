"""What the neighbourhood ingestion must guarantee.

These two files exist for one job: they are the only published documents that
cut the two boroughs APCIQ cuts, and 240 960 people are placed in a sector on
the strength of them. So the parser is tested on real extracts of both files
rather than on stubs -- a fixture I invent can only contain the shape I already
expect.

The test worth reading twice is
`test_a_linked_city_gets_no_borough_code_rather_than_a_broken_one`. Fourteen
features of the housing-reference file carry no borough code, because a linked
city has no borough. A parser that concatenated the prefix anyway would produce
the string 'REMNone', which joins to nothing, looks like a code, and would sit
in the raw layer until somebody wondered why a borough was missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.montreal_open_data import ckan, datasets, load

FIXTURES = Path(__file__).parent / "fixtures"

SOCIOLOGICAL = FIXTURES / "quartiers_sociologiques_2014.geojson"
HOUSING = FIXTURES / "quartierreferencehabitation.geojson"


@pytest.fixture(scope="module")
def sociological_document() -> dict:
    return json.loads(SOCIOLOGICAL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def housing_document() -> dict:
    return json.loads(HOUSING.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Reading the files. No network, no database.
# ---------------------------------------------------------------------------


def test_the_sociological_file_separates_the_two_halves_of_one_borough(
    sociological_document,
):
    """The whole reason this file is in the project.

    Côte-des-Neiges–Notre-Dame-de-Grâce is one borough in every administrative
    file, and APCIQ treats its two halves as separate sectors, 8 and 7. Nothing
    else published names them apart.
    """
    features = ckan.neighbourhoods_from(
        sociological_document, datasets.SOCIOLOGICAL_NEIGHBOURHOODS
    )
    by_code = {f.neighbourhood_code: f for f in features}

    assert by_code["4"].neighbourhood_name == "Côte-des-Neiges"
    assert by_code["5"].neighbourhood_name == "Notre-Dame-de-Grâce"

    # Both name the SAME borough in their own wording, which is exactly why
    # the seed addresses them by code and never by this string.
    assert by_code["4"].borough_name_source == by_code["5"].borough_name_source


def test_the_housing_file_isolates_ile_des_soeurs_from_the_rest_of_verdun(
    housing_document,
):
    """The second cut, and the reason one file was not enough.

    The sociological file carries a single polygon for the whole of Verdun and
    cannot make this distinction. APCIQ puts Ile-des-Soeurs in sector 10 and the
    rest of the borough in sector 4.
    """
    features = ckan.neighbourhoods_from(housing_document, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)
    verdun = {f.neighbourhood_code: f for f in features if f.borough_code == "REM12"}

    assert set(verdun) == {"64", "65", "66"}
    assert verdun["65"].neighbourhood_name == "Ile-des-Soeurs"


def test_the_borough_code_is_derived_from_a_published_code_not_from_a_name(
    housing_document,
):
    """'REM' || no_arr lands on the codes this project already uses.

    Verified against all 19 boroughs on 2026-08-24: none missing, none extra.
    That is what lets a neighbourhood reach dim_geography without any two names
    ever being compared -- the name join this project refuses.
    """
    features = ckan.neighbourhoods_from(housing_document, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)
    by_code = {f.neighbourhood_code: f for f in features}

    assert by_code["64"].borough_code == "REM12"   # Verdun
    assert by_code["60A"].borough_code == "REM16"  # Montréal-Nord


def test_a_linked_city_gets_no_borough_code_rather_than_a_broken_one(housing_document):
    """A linked city has no borough, so the code must be absent, not invented.

    Fourteen features are in this position. The failure this guards against is
    a string like 'REMNone': it joins to nothing, it looks like a code, and it
    would sit in the raw layer looking plausible.
    """
    features = ckan.neighbourhoods_from(housing_document, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)
    westmount = next(f for f in features if f.neighbourhood_code == "81")

    assert westmount.neighbourhood_name == "Westmount"
    assert westmount.borough_code is None
    assert westmount.municipality_name_source == "Westmount"


def test_the_sociological_file_yields_no_borough_code_at_all(sociological_document):
    """That file publishes no borough code, so none is derived.

    Its borough NAME is right there and matching it against another file's
    spelling is precisely the join this project refuses. A NULL is the honest
    answer, and nothing downstream needs the column: the seed addresses these
    polygons by their published id.
    """
    features = ckan.neighbourhoods_from(
        sociological_document, datasets.SOCIOLOGICAL_NEIGHBOURHOODS
    )

    assert all(f.borough_code is None for f in features)
    assert all(f.borough_name_source for f in features)


def test_a_code_with_a_letter_stays_text(housing_document):
    """Montréal-Nord numbers three of its neighbourhoods 60A, 60B, 60C.

    A loader that treated the code as a number would lose them, and they are
    not special cases to be dropped -- they are how the file is written.
    """
    features = ckan.neighbourhoods_from(housing_document, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)

    assert any(f.neighbourhood_code == "60A" for f in features)


def test_every_property_reaches_the_raw_layer_verbatim(sociological_document):
    """The two files share no attribute at all, so none is selected away.

    This project has already paid once for an attribute discarded at load time
    that had to be fetched again later.
    """
    features = ckan.neighbourhoods_from(
        sociological_document, datasets.SOCIOLOGICAL_NEIGHBOURHOODS
    )
    stored = json.loads(features[0].properties_json)
    original = next(
        f["properties"]
        for f in sociological_document["features"]
        if str(f["properties"]["id"]) == features[0].neighbourhood_code
    )

    assert stored == original


def test_a_feature_without_its_published_code_stops_the_load(sociological_document):
    """A polygon with no code cannot be placed, and must not be guessed at.

    The seed addresses polygons by code. A row keyed on nothing would be a row
    a sector could silently attach to.
    """
    broken = json.loads(json.dumps(sociological_document))
    del broken["features"][0]["properties"]["id"]

    with pytest.raises(ckan.SourceShapeError, match="id"):
        ckan.neighbourhoods_from(broken, datasets.SOCIOLOGICAL_NEIGHBOURHOODS)


def test_duplicate_codes_stop_the_load(housing_document):
    """Two polygons under one code would make a sector depend on row order.

    The raw table keys on (source_dataset, neighbourhood_code), so the load
    would otherwise fail halfway through -- or worse, keep whichever row landed
    last and attach 21 568 residents to it.
    """
    broken = json.loads(json.dumps(housing_document))
    broken["features"][1]["properties"]["no_qr"] = broken["features"][0]["properties"]["no_qr"]

    with pytest.raises(ckan.SourceShapeError, match="not unique"):
        ckan.neighbourhoods_from(broken, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)


@pytest.mark.parametrize("path", [SOCIOLOGICAL, HOUSING])
def test_both_files_declare_the_projection_the_project_expects(path):
    """CRS84, checked before a row is written, on every run.

    The boundary dataset of this same portal also publishes a NAD83 variant in
    metres. It loads without error and makes every spatial join return nothing.
    """
    document = json.loads(path.read_text(encoding="utf-8"))

    assert ckan.check_crs(document) == datasets.EXPECTED_CRS


# ---------------------------------------------------------------------------
# Against the real database, inside a transaction that is always rolled back.
# ---------------------------------------------------------------------------


@pytest.mark.db
def test_loading_the_same_file_twice_changes_nothing(db_connection, housing_document):
    """Idempotence, and where it actually comes from.

    Not from this code: from the primary key (source_dataset,
    neighbourhood_code) declared on the table. The WHERE clause on DO UPDATE is
    what keeps updated_at meaningful -- an unchanged file rewrites no row, and
    the count comes back from the database rather than from a counter kept in
    Python.
    """
    features = ckan.neighbourhoods_from(housing_document, datasets.HOUSING_REFERENCE_NEIGHBOURHOODS)

    first = load.load_neighbourhoods(
        db_connection,
        features,
        source_dataset=datasets.HOUSING_REFERENCE_NEIGHBOURHOODS.key,
        source_crs=datasets.EXPECTED_CRS,
    )
    second = load.load_neighbourhoods(
        db_connection,
        features,
        source_dataset=datasets.HOUSING_REFERENCE_NEIGHBOURHOODS.key,
        source_crs=datasets.EXPECTED_CRS,
    )

    # The fixture holds real rows that are already loaded, so the first pass
    # updates nothing either. What matters is that neither pass INSERTS.
    assert first.inserted == 0
    assert second.inserted == 0
    assert second.updated == 0


@pytest.mark.db
def test_the_two_seeded_boroughs_are_the_only_ones_apciq_splits(db_connection):
    """The seed must cover every entity that needs cutting, and no other.

    If APCIQ ever split a third borough, the seed would be silently incomplete:
    those points would resolve to no sector and their residents would vanish
    from the bridge. The conservation test would catch the symptom; this one
    names the cause.
    """
    with db_connection.cursor() as cur:
        cur.execute(
            """
            select codemamh
              from marts.bridge_apciq_sector_geography
             group by codemamh
            having count(*) > 1
             order by codemamh
            """
        )
        split_by_apciq = {row[0] for row in cur.fetchall()}

        cur.execute("select distinct borough_codemamh from marts.apciq_sector_neighbourhood")
        covered_by_seed = {row[0] for row in cur.fetchall()}

    assert split_by_apciq == {"REM12", "REM34"}
    assert covered_by_seed == split_by_apciq
