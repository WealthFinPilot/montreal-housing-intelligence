"""Talks to the Données Montréal portal. Knows nothing about the database.

Split the same way as the Bank of Canada modules: everything here either makes
an HTTP call or transforms what came back, and none of it can write a row.
`declared_crs()` and `features_from()` are pure functions over a parsed
document, so the tests cover the interesting logic with the sample file on
disk, offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from . import datasets as catalogue

TIMEOUT_SECONDS = 120


class SourceShapeError(RuntimeError):
    """The source answered, but not with what this module knows how to read.

    Raised rather than worked around. A boundary file whose shape changed is
    news, not noise, and guessing at it is how a project ends up with silently
    wrong geography.
    """


@dataclass(frozen=True)
class BoundaryFeature:
    """One administrative entity, still exactly as the file spells it."""

    codemamh: str
    codeid: str | None
    nom: str | None
    num: str | None
    abrev: str | None
    entity_type: str | None
    comment: str | None
    datemodif: str | None
    geometry_geojson: str


def resolve_resource_url(dataset: catalogue.Dataset, session: requests.Session | None = None) -> str:
    """Ask CKAN for the current download URL of this dataset's file.

    Matched on the filename at the end of the URL rather than on position or
    format -- see the header of datasets.py for what that protects against.
    The CKAN API needs no special User-Agent; the download itself does.
    """
    session = session or requests.Session()
    response = session.get(
        f"{catalogue.CKAN_BASE}/api/3/action/package_show",
        params={"id": dataset.package_id},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    resources = response.json()["result"]["resources"]

    matches = [r for r in resources if r.get("url", "").endswith("/" + dataset.filename)]
    if len(matches) != 1:
        available = sorted(r.get("url", "").rsplit("/", 1)[-1] for r in resources)
        raise SourceShapeError(
            f"expected exactly one resource named {dataset.filename} in package "
            f"{dataset.package_id}, found {len(matches)}. Available: {available}"
        )
    return matches[0]["url"]


def fetch_geojson(url: str, session: requests.Session | None = None) -> dict[str, Any]:
    """Download and parse the file. The browser User-Agent is not optional."""
    session = session or requests.Session()
    response = session.get(
        url,
        headers={"User-Agent": catalogue.BROWSER_USER_AGENT},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def declared_crs(document: dict[str, Any]) -> str:
    """The coordinate reference system the file states.

    A GeoJSON with no `crs` member is WGS84 by RFC 7946, so its absence is an
    answer, not a gap -- but this project prefers the source to say it out
    loud, and this dataset does.
    """
    crs = document.get("crs")
    if crs is None:
        return "urn:ogc:def:crs:OGC:1.3:CRS84"  # RFC 7946 default
    try:
        return crs["properties"]["name"]
    except (KeyError, TypeError) as exc:
        raise SourceShapeError(f"cannot read the crs member: {crs!r}") from exc


def check_crs(document: dict[str, Any], expected: str = catalogue.EXPECTED_CRS) -> str:
    """Refuse to go further if the projection is not the expected one.

    This is the check that turns an invisible failure into a loud one. The
    same dataset publishes a NAD83 variant whose coordinates are metres; it
    would load without complaint and make every spatial join return nothing.
    """
    found = declared_crs(document)
    if found != expected:
        raise SourceShapeError(
            f"wrong coordinate reference system: expected {expected}, file declares "
            f"{found}. Loading it would put projected coordinates where degrees "
            "are expected, and spatial joins would quietly return no rows."
        )
    return found


def features_from(document: dict[str, Any]) -> list[BoundaryFeature]:
    """Turn the FeatureCollection into rows, changing nothing.

    Attribute values are passed through as text. The geometry member is
    re-serialised compactly and handed on as a string: PostGIS converts it in
    the staging model, where a failure stops a build instead of being swallowed
    by an ingestion script.
    """
    if document.get("type") != "FeatureCollection":
        raise SourceShapeError(f"expected a FeatureCollection, got {document.get('type')!r}")

    features = []
    for index, feature in enumerate(document.get("features", [])):
        properties = feature.get("properties") or {}
        code = properties.get("CODEMAMH")
        if not code:
            raise SourceShapeError(
                f"feature {index} has no CODEMAMH. It is the primary key of "
                "raw.mtl_administrative_boundary and the join to the MAMH roll; "
                "a row without one cannot be placed."
            )
        geometry = feature.get("geometry")
        if not geometry:
            raise SourceShapeError(f"feature {index} ({code}) carries no geometry")

        features.append(
            BoundaryFeature(
                codemamh=str(code),
                codeid=_text(properties.get("CODEID")),
                nom=_text(properties.get("NOM")),
                num=_text(properties.get("NUM")),
                abrev=_text(properties.get("ABREV")),
                entity_type=_text(properties.get("TYPE")),
                comment=_text(properties.get("COMMENT")),
                datemodif=_text(properties.get("DATEMODIF")),
                geometry_geojson=json.dumps(geometry, separators=(",", ":")),
            )
        )

    duplicates = _duplicated([f.codemamh for f in features])
    if duplicates:
        raise SourceShapeError(
            f"CODEMAMH is not unique in this file: {duplicates}. The raw table "
            "keys on it, so the load would fail halfway through instead."
        )
    return features


def _text(value: Any) -> str | None:
    """Everything reaches the raw layer as text, except a real absence."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _duplicated(values: list[str]) -> list[str]:
    seen: set[str] = set()
    twice: list[str] = []
    for value in values:
        if value in seen and value not in twice:
            twice.append(value)
        seen.add(value)
    return twice


@dataclass(frozen=True)
class NeighbourhoodFeature:
    """One neighbourhood polygon, still exactly as its file spells it."""

    neighbourhood_code: str
    neighbourhood_name: str | None
    borough_code: str | None
    borough_name_source: str | None
    municipality_name_source: str | None
    properties_json: str
    geometry_geojson: str


def neighbourhoods_from(
    document: dict[str, Any],
    dataset: catalogue.NeighbourhoodDataset,
) -> list[NeighbourhoodFeature]:
    """Turn a neighbourhood FeatureCollection into rows, changing nothing.

    Which property holds the code and which holds the name is read from the
    catalogue rather than guessed, so a file that renames a column fails here
    with a message naming the file, instead of loading rows keyed on None.
    """
    if document.get("type") != "FeatureCollection":
        raise SourceShapeError(f"expected a FeatureCollection, got {document.get('type')!r}")

    features: list[NeighbourhoodFeature] = []
    for index, feature in enumerate(document.get("features", [])):
        properties = feature.get("properties") or {}

        code = _text(properties.get(dataset.code_property))
        if not code:
            raise SourceShapeError(
                f"{dataset.key}: feature {index} has no {dataset.code_property!r}. "
                "That property is the primary key of raw.mtl_neighbourhood and "
                "the only thing a seed may address a polygon by; a row without "
                "one cannot be placed."
            )

        geometry = feature.get("geometry")
        if not geometry:
            raise SourceShapeError(f"{dataset.key}: feature {index} ({code}) carries no geometry")

        # The borough code, derived from a published code or not derived at all.
        borough_code = None
        if dataset.borough_code_property:
            published = _text(properties.get(dataset.borough_code_property))
            # A missing value is not a fault: the 14 linked-city features of the
            # housing-reference file have no borough, because a linked city has
            # none. Absent stays absent.
            borough_code = f"REM{published}" if published else None

        features.append(
            NeighbourhoodFeature(
                neighbourhood_code=code,
                neighbourhood_name=_text(properties.get(dataset.name_property)),
                borough_code=borough_code,
                borough_name_source=_text(properties.get(dataset.borough_name_property))
                if dataset.borough_name_property
                else None,
                municipality_name_source=_text(
                    properties.get(dataset.municipality_name_property)
                )
                if dataset.municipality_name_property
                else None,
                properties_json=json.dumps(properties, ensure_ascii=False, sort_keys=True),
                geometry_geojson=json.dumps(geometry, separators=(",", ":")),
            )
        )

    duplicates = _duplicated([f.neighbourhood_code for f in features])
    if duplicates:
        raise SourceShapeError(
            f"{dataset.key}: {dataset.code_property} is not unique in this file: "
            f"{duplicates}. The raw table keys on it, and a seed addresses "
            "polygons by it, so a duplicate would attach a sector to whichever "
            "row happened to land last."
        )
    return features
