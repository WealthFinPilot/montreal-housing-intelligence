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
