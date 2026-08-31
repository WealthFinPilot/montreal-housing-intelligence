"""Ask the Statistics Canada WDS API for one published series. No database.

Same split as valet.py and ckan.py: this module speaks HTTP and knows nothing
about tables, so it can be exercised without a database and the loader can be
exercised without a network.

WHY FOUR REQUESTS AND NOT ONE
-----------------------------
A coordinate is a POSITION in a cube -- ten dimension member ids joined by
dots. It is not a name. If Statistics Canada re-cuts the cube, "13.2.0..."
keeps working and quietly starts pointing at a different city or a different
basket. Nothing fails; the wrong index just loads. That is the same failure
the boundary download guards against by checking the filename it was served.

So the coordinate is never trusted on its own:

  1. getCubeMetadata     -- does member 13 of the geography dimension really
                            carry classification 462, and is member 2 of the
                            product dimension really "All-items"? This checks
                            the coordinate against what the source publishes.
  2. ...LatestNPeriods   -- what vector does that coordinate resolve to? It
                            must be the one the catalogue declares.
  3. ...ByReferencePeriodRange
                         -- the observations, by date range rather than by
                            "latest N", which would need a count that changes
                            every month.
  4. getCodeSets         -- what the numeric codes and the unit mean, so the
                            base of the index is recorded rather than typed
                            from memory.

Attribution
-----------
Source: Statistics Canada, table 18100004. Statistics Canada Open Licence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ingestion.statcan.datasets import SeriesDataset

WDS = "https://www150.statcan.gc.ca/t1/wds/rest"

TIMEOUT = 90


class WdsError(RuntimeError):
    """The API answered, but not with what was asked for."""


@dataclass(frozen=True)
class SeriesResponse:
    """Everything one series fetch produced, ready for parse.py."""

    vector_id: str
    points: list[dict[str, Any]]
    uom_code: str
    uom: str
    cube_title: str
    cube_end_date: str
    source_url: str


def _post(session: requests.Session, endpoint: str, body: list[dict]) -> Any:
    response = session.post(f"{WDS}/{endpoint}", json=body, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not payload or payload[0].get("status") != "SUCCESS":
        raise WdsError(
            f"{endpoint} did not return SUCCESS: "
            f"{payload[0].get('status') if payload else 'empty response'}"
        )
    return payload[0]["object"]


def _get(session: requests.Session, endpoint: str, params: dict) -> Any:
    response = session.get(f"{WDS}/{endpoint}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):          # getCodeSets answers as an object
        return payload["object"]
    if not payload or payload[0].get("status") != "SUCCESS":
        raise WdsError(f"{endpoint} did not return SUCCESS")
    return payload[0]["object"]


def _verify_coordinate(dataset: SeriesDataset, metadata: dict) -> str:
    """Check the coordinate names what the catalogue says, return the uom code.

    Reads the two dimension members the coordinate selects and compares them
    with the geography and product the catalogue declares. A cube re-cut moves
    members; this is what turns that from a silent substitution into a stop.
    """
    wanted = dataset.coordinate.split(".")
    uom_code: str | None = None

    for dimension in metadata["dimension"]:
        position = dimension["dimensionPositionId"]
        if position > len(wanted):
            continue
        member_id = int(wanted[position - 1])
        if member_id == 0:
            continue
        member = next(
            (m for m in dimension["member"] if m["memberId"] == member_id), None
        )
        if member is None:
            raise WdsError(
                f"coordinate position {position} asks for member {member_id}, "
                f"which no longer exists in dimension "
                f"'{dimension['dimensionNameEn']}'"
            )
        name = member["memberNameEn"]

        if position == 1:
            # Geography. Compared on the PUBLISHED classification code, not on
            # the name -- the project has refused name joins since J3.1.
            classification = str(member.get("classificationCode") or "")
            if classification != "462":
                raise WdsError(
                    f"coordinate geography member {member_id} carries "
                    f"classification '{classification}', not 462. It resolves "
                    f"to '{name}'."
                )
        if position == 2:
            if name != dataset.product_name:
                raise WdsError(
                    f"coordinate product member {member_id} is '{name}', not "
                    f"'{dataset.product_name}'"
                )
            uom_code = str(member.get("memberUomCode"))

    if uom_code is None:
        raise WdsError("the product member declared no unit of measure")
    return uom_code


def fetch_series(dataset: SeriesDataset, *, session: requests.Session) -> SeriesResponse:
    """Fetch one series, having proved it is the series that was asked for."""
    metadata = _post(session, "getCubeMetadata", [{"productId": dataset.product_id}])
    uom_code = _verify_coordinate(dataset, metadata)

    resolved = _post(
        session,
        "getDataFromCubePidCoordAndLatestNPeriods",
        [{"productId": dataset.product_id, "coordinate": dataset.coordinate, "latestN": 1}],
    )
    vector_id = str(resolved["vectorId"])
    if vector_id != dataset.expected_vector_id:
        raise WdsError(
            f"coordinate {dataset.coordinate} resolves to vector {vector_id}, "
            f"but the catalogue declares {dataset.expected_vector_id}. The "
            "cube has been re-cut: confirm what the coordinate now selects "
            "before loading anything."
        )

    # The end of the range is taken from the cube's own metadata rather than
    # from today's date. The source states how far it publishes; asking beyond
    # that would be inventing a period, and hard-coding one would go stale.
    end_period = str(metadata.get("cubeEndDate") or "")
    if not end_period:
        raise WdsError("the cube declares no end date, so no range can be asked for")

    source_url = (
        f"{WDS}/getDataFromVectorByReferencePeriodRange"
        f"?vectorIds={vector_id}"
        f"&startRefPeriod={dataset.start_period}"
        f"&endReferencePeriod={end_period}"
    )
    series = _get(
        session,
        "getDataFromVectorByReferencePeriodRange",
        {
            "vectorIds": f'"{vector_id}"',
            "startRefPeriod": dataset.start_period,
            "endReferencePeriod": end_period,
        },
    )

    code_sets = _get(session, "getCodeSets", {})
    uom = next(
        (u["memberUomEn"] for u in code_sets["uom"]
         if str(u["memberUomCode"]) == uom_code),
        "",
    )

    return SeriesResponse(
        vector_id=vector_id,
        points=series["vectorDataPoint"],
        uom_code=uom_code,
        uom=uom or "",
        cube_title=metadata.get("cubeTitleEn", ""),
        cube_end_date=metadata.get("cubeEndDate", ""),
        source_url=source_url,
    )
