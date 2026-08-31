"""Write the shape files the Power BI Shape map visual needs.

WHY THIS SCRIPT EXISTS

Power BI's Shape map does not geocode anything and does not call any external
service: it colours a shape file you hand it. That file has to come from
somewhere, and the only authoritative source for these outlines is
`marts.dim_geography` -- the same table the report reads its numbers from.
Generating the file from the database rather than downloading a lookalike is
what keeps the shapes and the figures on the same geography.

WHAT IT PRODUCES

Two GeoJSON FeatureCollections, each Feature carrying exactly ONE property:

    census_tract_island.geojson    541 tracts, keyed on `ct_uid`
    apciq_sector_island.geojson     18 sectors, keyed on `sector_id`

    One property, deliberately. Microsoft documents "View map type key" as the
    way to check that the file's keys match the Location field, but it does not
    document which property it picks when a Feature carries several. With a
    single property there is nothing to pick, so the behaviour cannot surprise
    us later.

The sector file is the SMALLER of the two -- 18 shapes against 541, because the
union erases every internal border. Two of the report's maps share it, so the
reader learns the island's silhouette once and then compares a price to a
verdict on the same outline.

THE TRAP THIS FILE IS BUILT TO AVOID

A census tract identifier looks like a number and is not one: `4620001.00`.
Written as a JSON number it becomes 4620001 and the trailing `.00` is gone --
the file loads without error and joins to nothing. Every key here is written as
a JSON string, and the script refuses to write a file where that is not true.

USAGE (Git Bash or PowerShell, from the repository root, tunnel open)

    .venv/Scripts/python.exe scripts/export_map_shapes.py
    .venv/Scripts/python.exe scripts/export_map_shapes.py --layer sectors
    .venv/Scripts/python.exe scripts/export_map_shapes.py --decimals 5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.db import connection_kwargs  # noqa: E402

SHAPES_DIR = REPO_ROOT / "powerbi" / "shapes"

# 6 decimal places is roughly 0.11 m at this latitude -- far finer than the
# source, and it is what the feasibility study measured at 1.27 MB for the
# tracts. Coarser rounding saves under 10 %, which is not worth moving points
# for.
DEFAULT_DECIMALS = 6

SHAPES = """
select geography_code,
       st_asgeojson(geometry, %(decimals)s) as geometry_json
from marts.dim_geography
where geography_type = %(geography_type)s
  and geometry is not null
order by geography_code
"""


@dataclass(frozen=True)
class Layer:
    """One shape file: what to select, what to call the key, how many to expect."""

    name: str
    geography_type: str
    key_property: str
    expected: int
    # A tract id must keep its decimals or it joins to nothing. A sector number
    # has none, so demanding one would reject a correct file.
    key_has_decimals: bool
    filename: str


LAYERS = {
    "tracts": Layer(
        name="census tracts",
        geography_type="census_tract",
        key_property="ct_uid",
        expected=541,
        key_has_decimals=True,
        filename="census_tract_island.geojson",
    ),
    "sectors": Layer(
        name="APCIQ sectors",
        geography_type="apciq_sector",
        key_property="sector_id",
        expected=18,
        key_has_decimals=False,
        filename="apciq_sector_island.geojson",
    ),
}


def build_feature_collection(rows: list[tuple[str, str]], layer: Layer) -> dict:
    """Wrap each PostGIS geometry in a Feature carrying its id as a string."""
    features = []
    for geography_code, geometry_json in rows:
        features.append(
            {
                "type": "Feature",
                # str() is not defensive noise: the whole file is useless if this
                # value is ever emitted as a JSON number.
                "properties": {layer.key_property: str(geography_code)},
                "geometry": json.loads(geometry_json),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def check(collection: dict, layer: Layer) -> list[str]:
    """Everything that must hold before the file is worth loading into Power BI."""
    problems = []
    features = collection["features"]

    if len(features) != layer.expected:
        problems.append(f"expected {layer.expected} features, built {len(features)}")

    keys = [f["properties"][layer.key_property] for f in features]

    non_string = [k for k in keys if not isinstance(k, str)]
    if non_string:
        problems.append(f"{len(non_string)} keys are not strings, e.g. {non_string[:3]}")

    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} duplicate keys")

    if layer.key_has_decimals:
        # A tract id that lost its decimals joins to nothing, silently.
        without_decimals = [k for k in keys if "." not in k]
        if without_decimals:
            problems.append(
                f"{len(without_decimals)} keys carry no decimal point, "
                f"e.g. {without_decimals[:3]} -- they would not join"
            )

    empty = [f["properties"][layer.key_property] for f in features if not f["geometry"]]
    if empty:
        problems.append(f"{len(empty)} features have no geometry, e.g. {empty[:3]}")

    return problems


def export(cur, layer: Layer, decimals: int, output: Path) -> int:
    """Build, check and write one layer. Returns 0 on success, 1 on refusal."""
    cur.execute(SHAPES, {"decimals": decimals, "geography_type": layer.geography_type})
    collection = build_feature_collection(cur.fetchall(), layer)

    problems = check(collection, layer)
    if problems:
        print(f"REFUSED -- {output.name} was not written:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    # separators without spaces: this file is read by a machine, and the spaces
    # would add roughly 10 % for nobody's benefit.
    text = json.dumps(collection, separators=(",", ":"), ensure_ascii=False)
    output.write_text(text, encoding="utf-8")

    keys = [f["properties"][layer.key_property] for f in collection["features"]]
    print(f"Wrote {output.relative_to(REPO_ROOT)}")
    print(f"  layer      {layer.name}")
    print(f"  features   {len(collection['features'])}")
    print(f"  size       {len(text.encode('utf-8')) / 1024:.0f} kB")
    print(f"  key        {layer.key_property}: {keys[0]!r} .. {keys[-1]!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layer",
        choices=sorted(LAYERS) + ["all"],
        default="all",
        help="which shape file to write (default: both)",
    )
    parser.add_argument("--output-dir", type=Path, default=SHAPES_DIR)
    parser.add_argument("--decimals", type=int, default=DEFAULT_DECIMALS)
    args = parser.parse_args()

    chosen = sorted(LAYERS) if args.layer == "all" else [args.layer]

    failures = 0
    with psycopg.connect(**connection_kwargs()) as conn:
        with conn.cursor() as cur:
            for key in chosen:
                layer = LAYERS[key]
                failures += export(
                    cur, layer, args.decimals, args.output_dir / layer.filename
                )
                print()
        conn.rollback()

    if failures:
        return 1

    print("In Power BI, these keys must match dim_geography[geography_code] exactly.")
    print("Check with Format visual > Map settings > View map type key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
