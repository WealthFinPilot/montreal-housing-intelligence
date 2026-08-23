"""What the Montréal boundary ingestion must guarantee.

The offline tests run against sample_data/mtl_limites_administratives.geojson,
the real file downloaded on 2026-08-21. Using the actual document rather than a
hand-made stub is the point: a fixture I invent can only contain the shape I
already expect.

The one test worth reading twice is
`test_a_file_in_the_wrong_projection_is_refused`. That failure has no symptom
of its own -- the rows load, the geometries are valid, and every spatial join
silently returns nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.montreal_open_data import ckan, datasets, load

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "mtl_limites_administratives.geojson"


@pytest.fixture(scope="module")
def document() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Reading the file. No network, no database.
# ---------------------------------------------------------------------------


def test_the_island_is_thirty_four_entities(document):
    features = ckan.features_from(document)

    assert len(features) == 34
    kinds = {}
    for feature in features:
        kinds[feature.entity_type] = kinds.get(feature.entity_type, 0) + 1
    assert kinds == {"Arrondissement": 19, "Ville liée": 15}


def test_codemamh_carries_two_nomenclatures_at_once(document):
    """The single most useful fact about this file.

    A linked city is identified by its 5-digit MAMH municipality code, a
    borough by a REMxx code -- and the MAMH assessment roll already extracted
    carries both, in municipality_code and borough_code respectively. That is
    what lets geography join to the roll without matching on names.
    """
    by_code = {f.codemamh: f for f in ckan.features_from(document)}

    assert by_code["66112"].entity_type == "Ville liée"
    assert by_code["66112"].nom == "Baie-D'Urfé"
    assert by_code["REM19"].entity_type == "Arrondissement"
    assert by_code["REM19"].nom == "Ville-Marie"

    linked_cities = [f for f in by_code.values() if f.entity_type == "Ville liée"]
    assert all(f.codemamh.isdigit() and len(f.codemamh) == 5 for f in linked_cities)

    boroughs = [f for f in by_code.values() if f.entity_type == "Arrondissement"]
    assert all(f.codemamh.startswith("REM") for f in boroughs)


def test_codemamh_is_unique_because_it_is_the_primary_key(document):
    codes = [f.codemamh for f in ckan.features_from(document)]

    assert len(codes) == len(set(codes))


def test_geometry_survives_as_text(document):
    features = ckan.features_from(document)

    for feature in features:
        geometry = json.loads(feature.geometry_geojson)
        assert geometry["type"] == "MultiPolygon"
        assert geometry["coordinates"]


# ---------------------------------------------------------------------------
# Refusing what should not be loaded.
# ---------------------------------------------------------------------------


def test_a_file_in_the_wrong_projection_is_refused(document):
    """The trap this whole module is shaped around.

    The same CKAN dataset publishes a NAD83 GeoJSON, and the API lists it
    first. Its coordinates are metres. Nothing about loading it raises: the
    geometries are valid, the row count is right, and every ST_Intersects
    against a WGS84 geometry afterwards returns nothing at all.
    """
    nad83 = dict(document)
    nad83["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32188"}}

    with pytest.raises(ckan.SourceShapeError, match="coordinate reference system"):
        ckan.check_crs(nad83)


def test_the_expected_projection_is_accepted(document):
    assert ckan.check_crs(document) == datasets.EXPECTED_CRS


def test_a_feature_without_codemamh_stops_the_load():
    crippled = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"NOM": "Nowhere"}, "geometry": {"type": "Point", "coordinates": [0, 0]}}
        ],
    }

    with pytest.raises(ckan.SourceShapeError, match="CODEMAMH"):
        ckan.features_from(crippled)


def test_duplicated_codemamh_stops_the_load():
    twice = {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {"CODEMAMH": "REM19", "NOM": "Ville-Marie"},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            },
            {
                "properties": {"CODEMAMH": "REM19", "NOM": "Ville-Marie again"},
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            },
        ],
    }

    with pytest.raises(ckan.SourceShapeError, match="not unique"):
        ckan.features_from(twice)


# ---------------------------------------------------------------------------
# Against the real database, inside a transaction that is rolled back.
# ---------------------------------------------------------------------------


@pytest.mark.db
def test_loading_the_same_file_twice_changes_nothing_the_second_time(db_connection, document):
    """Acceptance criterion 2 of J2, applied to this source.

    The evidence is 0 inserted and 0 updated, and it comes from the database:
    PostgreSQL reports which rows it actually touched, the script does not
    count them itself.
    """
    from src import migrations

    migrations.run(db_connection)  # the table may not exist on a fresh database
    features = ckan.features_from(document)

    first = load.load_boundaries(
        db_connection,
        features,
        source_dataset="test_only__boundaries",
        source_crs=datasets.EXPECTED_CRS,
    )
    second = load.load_boundaries(
        db_connection,
        features,
        source_dataset="test_only__boundaries",
        source_crs=datasets.EXPECTED_CRS,
    )

    assert first.total == 34
    assert (second.inserted, second.updated) == (0, 0)


@pytest.mark.db
def test_a_changed_attribute_is_an_update_not_a_duplicate(db_connection, document):
    from src import migrations

    migrations.run(db_connection)
    features = ckan.features_from(document)

    load.load_boundaries(
        db_connection,
        features,
        source_dataset="test_only__boundaries",
        source_crs=datasets.EXPECTED_CRS,
    )

    renamed = [
        f if f.codemamh != "REM19" else type(f)(**{**f.__dict__, "nom": "Ville-Marie (renamed)"})
        for f in features
    ]
    again = load.load_boundaries(
        db_connection,
        renamed,
        source_dataset="test_only__boundaries",
        source_crs=datasets.EXPECTED_CRS,
    )

    assert (again.inserted, again.updated) == (0, 1)

    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM raw.mtl_administrative_boundary"
            " WHERE source_dataset = 'test_only__boundaries'"
        )
        assert cur.fetchone()[0] == 34
