"""The Données Montréal datasets this project ingests.

Every value below was read from a response received on 2026-08-23, not
recalled. The verification trail:

  GET https://donnees.montreal.ca/api/3/action/package_show
      ?id=limites-administratives-agglomeration                        -> 200
  GET .../download/limites-administratives-agglomeration.geojson       -> 200,
      1 258 670 bytes, 34 features, CRS84

THE TRAP THIS MODULE EXISTS TO AVOID
------------------------------------
The boundaries dataset publishes TWO GeoJSON resources, and the CKAN API lists
the wrong one first:

    1st: limites-administratives-agglomeration-nad83.geojson   1 470 723 B
    2nd: limites-administratives-agglomeration.geojson         1 258 670 B   <- this one

A script that grabs "the first GeoJSON resource" loads projected coordinates
in metres where the rest of the project expects degrees. Nothing raises: the
rows land, the geometries are valid, and every spatial join silently returns
nothing. So resources are addressed by FILENAME, and the declared CRS is
checked before a single row is written.

Resource UUIDs are deliberately not hard-coded: the portal can reissue them,
and the CKAN API resolves the current one on every run.
"""

from __future__ import annotations

from dataclasses import dataclass

CKAN_BASE = "https://donnees.montreal.ca"

# Downloads from this portal answer 403 with the body `RBAC: access denied`
# when the request carries a default programmatic User-Agent. The CKAN API
# itself does not care, but the file download does. Verified 2026-08-21.
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# What the file must declare. CRS84 is the axis-order-explicit spelling of
# EPSG:4326 -- longitude first, latitude second, degrees.
EXPECTED_CRS = "urn:ogc:def:crs:OGC:1.3:CRS84"

LICENCE = "CC-BY 4.0"
LICENCE_URL = "http://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "Source : Ville de Montréal, données ouvertes (CC-BY 4.0)"


@dataclass(frozen=True)
class Dataset:
    """One CKAN dataset, and how to pick the right file out of it."""

    key: str            # how this project refers to it, and what lands in source_dataset
    package_id: str     # the CKAN dataset name
    filename: str       # the exact file to take, not "the first GeoJSON"
    purpose: str
    expected_features: int | None = None  # logged and tested by dbt, not enforced here


BOUNDARIES = Dataset(
    key="limites-administratives-agglomeration",
    package_id="limites-administratives-agglomeration",
    filename="limites-administratives-agglomeration.geojson",
    purpose=(
        "The 34 administrative entities sharing the island of Montréal: the 19 "
        "boroughs of Ville de Montréal plus 15 linked cities. Backbone of "
        "dim_geography, and the only file carrying CODEMAMH, which joins to the "
        "MAMH assessment roll on both nomenclatures at once."
    ),
    expected_features=34,
)

DATASETS: tuple[Dataset, ...] = (BOUNDARIES,)


# ---------------------------------------------------------------------------
# Neighbourhood layers, added in J3.4
#
# Verified on 2026-08-24, by response and not by recall:
#
#   GET .../package_show?id=quartiers-sociologiques                  -> 200
#   GET .../download/quartiers_sociologiques_2014.geojson            -> 200,
#       292 280 bytes, 32 features, CRS84, `id` unique 32/32
#   GET .../package_show?id=quartiers                                -> 200
#   GET .../download/quartierreferencehabitation.geojson             -> 200,
#       1 135 769 bytes, 91 features, CRS84, `no_qr` unique 91/91
#
# Both declare CC-BY 4.0 in their CKAN licence field.
#
# These two exist for one job: they are the only published files that cut the
# two boroughs APCIQ cuts. Neither can do it alone -- see the header of
# sql/bootstrap/08_montreal_neighbourhood.sql.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NeighbourhoodDataset:
    """One neighbourhood file, and which of its properties carry what.

    The property names are per-file rather than shared because the two files
    have nothing in common: one says `id` / `Q_sociologique`, the other
    `no_qr` / `nom_qr`. Naming them here keeps ckan.py free of file-specific
    branching, and makes a renamed column fail with a message that says which
    file changed.
    """

    key: str
    package_id: str
    filename: str
    code_property: str              # the key the file publishes for each polygon
    name_property: str
    borough_name_property: str | None = None
    municipality_name_property: str | None = None

    # Present only where the file publishes a borough CODE. 'REM' || this value
    # is the borough code the rest of this project uses -- verified against all
    # 19 boroughs on 2026-08-24. Absent means the file has no code, and no
    # borough code is derived rather than one being guessed from a name.
    borough_code_property: str | None = None

    purpose: str = ""
    expected_features: int | None = None


SOCIOLOGICAL_NEIGHBOURHOODS = NeighbourhoodDataset(
    key="quartiers-sociologiques",
    package_id="quartiers-sociologiques",
    filename="quartiers_sociologiques_2014.geojson",
    code_property="id",
    name_property="Q_sociologique",
    borough_name_property="Arrondissement",
    purpose=(
        "The 32 sociological neighbourhoods, drawn in 2014 for community "
        "planning. The only published file naming Cote-des-Neiges and "
        "Notre-Dame-de-Grace as separate polygons, which is exactly the line "
        "APCIQ draws between its sectors 8 and 7."
    ),
    expected_features=32,
)

HOUSING_REFERENCE_NEIGHBOURHOODS = NeighbourhoodDataset(
    key="quartiers",
    package_id="quartiers",
    filename="quartierreferencehabitation.geojson",
    code_property="no_qr",
    name_property="nom_qr",
    borough_name_property="nom_arr",
    municipality_name_property="nom_mun",
    borough_code_property="no_arr",
    purpose=(
        "The 91 housing-reference neighbourhoods: the 19 boroughs subdivided, "
        "plus 14 linked cities each as a single polygon. The only published "
        "file isolating Ile-des-Soeurs -- APCIQ sector 10 -- from the rest of "
        "Verdun, which belongs to sector 4."
    ),
    expected_features=91,
)

NEIGHBOURHOOD_DATASETS: tuple[NeighbourhoodDataset, ...] = (
    SOCIOLOGICAL_NEIGHBOURHOODS,
    HOUSING_REFERENCE_NEIGHBOURHOODS,
)
