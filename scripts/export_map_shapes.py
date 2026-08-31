"""Write the census tract shape file the Power BI Shape map visual needs.

WHY THIS SCRIPT EXISTS

Power BI's Shape map does not geocode anything and does not call any external
service: it colours a shape file you hand it. That file has to come from
somewhere, and the only authoritative source for the 541 census tract outlines
of the island is `marts.dim_geography` -- the same table the report reads its
numbers from. Generating the file from the database rather than downloading a
lookalike is what keeps the shapes and the figures on the same geography.

WHAT IT PRODUCES

A GeoJSON FeatureCollection, one Feature per census tract, carrying exactly
ONE property: `ct_uid`.

    One property, deliberately. Microsoft documents "View map type key" as the
    way to check that the file's keys match the Location field, but it does not
    document which property it picks when a Feature carries several. With a
    single property there is nothing to pick, so the behaviour cannot surprise
    us later.

THE TRAP THIS FILE IS BUILT TO AVOID

A census tract identifier looks like a number and is not one: `4620001.00`.
Written as a JSON number it becomes 4620001 and the trailing `.00` is gone --
the file loads without error and joins to nothing. Every key here is written as
a JSON string, and the script refuses to write a file where that is not true.

USAGE (Git Bash or PowerShell, from the repository root, tunnel open)

    .venv/Scripts/python.exe scripts/export_map_shapes.py
    .venv/Scripts/python.exe scripts/export_map_shapes.py --decimals 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.db import connection_kwargs  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "powerbi" / "shapes" / "census_tract_island.geojson"

# 6 decimal places is roughly 0.11 m at this latitude -- far finer than the
# source, and it is what the feasibility study measured at 1.27 MB. Coarser
# rounding saves under 10 %, which is not worth moving points for.
DEFAULT_DECIMALS = 6

TRACTS = """
select geography_code,
       st_asgeojson(geometry, %(decimals)s) as geometry_json
from marts.dim_geography
where geography_type = 'census_tract'
  and geometry is not null
order by geography_code
"""

EXPECTED_TRACTS = 541


def build_feature_collection(rows: list[tuple[str, str]]) -> dict:
    """Wrap each PostGIS geometry in a Feature carrying its tract id as a string."""
    features = []
    for geography_code, geometry_json in rows:
        features.append(
            {
                "type": "Feature",
                # str() is not defensive noise: the whole file is useless if this
                # value is ever emitted as a JSON number.
                "properties": {"ct_uid": str(geography_code)},
                "geometry": json.loads(geometry_json),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def check(collection: dict, expected: int) -> list[str]:
    """Everything that must hold before the file is worth loading into Power BI."""
    problems = []
    features = collection["features"]

    if len(features) != expected:
        problems.append(f"expected {expected} features, built {len(features)}")

    keys = [f["properties"]["ct_uid"] for f in features]

    non_string = [k for k in keys if not isinstance(k, str)]
    if non_string:
        problems.append(f"{len(non_string)} keys are not strings, e.g. {non_string[:3]}")

    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} duplicate keys")

    # A tract id that lost its decimals joins to nothing, silently.
    without_decimals = [k for k in keys if "." not in k]
    if without_decimals:
        problems.append(
            f"{len(without_decimals)} keys carry no decimal point, "
            f"e.g. {without_decimals[:3]} -- they would not join"
        )

    empty = [f["properties"]["ct_uid"] for f in features if not f["geometry"]]
    if empty:
        problems.append(f"{len(empty)} features have no geometry, e.g. {empty[:3]}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decimals", type=int, default=DEFAULT_DECIMALS)
    parser.add_argument("--expected", type=int, default=EXPECTED_TRACTS)
    args = parser.parse_args()

    with psycopg.connect(**connection_kwargs()) as conn:
        with conn.cursor() as cur:
            cur.execute(TRACTS, {"decimals": args.decimals})
            rows = cur.fetchall()
        conn.rollback()

    collection = build_feature_collection(rows)

    problems = check(collection, args.expected)
    if problems:
        print("REFUSED -- the file was not written:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # separators without spaces: this file is read by a machine, and the spaces
    # would add roughly 10 % for nobody's benefit.
    text = json.dumps(collection, separators=(",", ":"), ensure_ascii=False)
    args.output.write_text(text, encoding="utf-8")

    keys = [f["properties"]["ct_uid"] for f in collection["features"]]
    print(f"Wrote {args.output.relative_to(REPO_ROOT)}")
    print(f"  features   {len(collection['features'])}")
    print(f"  size       {len(text.encode('utf-8')) / 1024:.0f} kB")
    print(f"  decimals   {args.decimals}")
    print(f"  key sample {keys[0]!r} .. {keys[-1]!r}")
    print("\nIn Power BI, these keys must match Census Tract[geography_code] exactly.")
    print("Check with Format visual > Map settings > View map type key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
