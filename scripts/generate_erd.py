"""Generate a drawDB-importable DDL of the analytical layer.

WHY THIS SCRIPT EXISTS
----------------------
The database declares exactly one foreign key -- raw.boc_observation.run_id ->
raw.pipeline_run.run_id -- across 38 tables. Everything in `staging` and
`marts` is built by dbt, which enforces referential integrity with
`relationships` TESTS rather than with constraints. That is a deliberate choice
(a mart is rebuilt, not mutated, so a constraint would only slow the rebuild
down), but it has a cost: a schema browser such as DBeaver has nothing to draw.

So the relationships have to be recovered from where they actually live, and
this script recovers them from two sources of truth, never from a human memory
of the model:

    columns and types  <- information_schema, on the live database
    relationships      <- the `relationships` tests in the dbt schema YAMLs

The output is a plain PostgreSQL DDL file. drawDB reads it through
File > Import from SQL (PostgreSQL dialect). Re-running the script after a
migration regenerates the file, which is what stops the diagram from quietly
becoming a lie.

WHAT THE DIAGRAM IS ALLOWED TO CLAIM
------------------------------------
Two kinds of edge end up in the picture, and they do not carry the same
guarantee. The constraint NAME says which is which, so the distinction survives
the round trip through drawDB:

    tested_*   a dbt `relationships` test asserts this edge on every build.
    derived_*  the edge is real and Power BI needs it, but no test asserts it
               HERE -- the same column is tested one table upstream, from which
               it is copied unchanged. Listed explicitly below, each with the
               upstream test that covers it. Never inferred from column names
               looking alike. --tested-only leaves them out entirely.

Usage (Git Bash, from the repo root, tunnel open):

    .venv/Scripts/python.exe scripts/generate_erd.py
    .venv/Scripts/python.exe scripts/generate_erd.py --star --keys-only --tested-only
    .venv/Scripts/python.exe scripts/generate_erd.py --layer all
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.db import connect  # noqa: E402

DBT_MODELS = REPO_ROOT / "dbt" / "models"
DEFAULT_OUT = REPO_ROOT / "docs" / "erd"

REF_PATTERN = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)")

# Tables come out of the database alphabetically, which scatters the star. Any
# table not named here keeps alphabetical order, after the ones that are: a new
# model appears in the diagram without anyone editing this list.
TABLE_ORDER = [
    "dim_date",
    "dim_geography",
    "dim_property_type",
    "dim_household_profile",
    "bridge_apciq_sector_geography",
    "bridge_census_tract_apciq_sector",
    "fact_market",
    "fact_market_trailing_12m",
    "fact_mortgage_scenario",
    "fact_affordability",
]

# Edges that the star schema needs and that dbt does not assert on this table,
# because the very same column is asserted one step upstream and copied down
# unchanged. Each one carries the upstream test that covers it, so a reader can
# check the claim instead of trusting it. Adding a line here is a decision, not
# a convenience: it puts an untested edge on a diagram.
DERIVED_EDGES = [
    (
        "fact_mortgage_scenario", "quarter_start_date", "dim_date", "date_key",
        "fact_mortgage_scenario.mortgage_scenario_key -> fact_market.market_key",
    ),
    (
        "fact_mortgage_scenario", "geography_key", "dim_geography", "geography_key",
        "fact_mortgage_scenario.mortgage_scenario_key -> fact_market.market_key",
    ),
    (
        "fact_mortgage_scenario", "property_type_code", "dim_property_type", "property_type_code",
        "fact_mortgage_scenario.mortgage_scenario_key -> fact_market.market_key",
    ),
    (
        "fact_affordability", "quarter_start_date", "dim_date", "date_key",
        "fact_market.quarter_start_date -> dim_date.date_key",
    ),
    (
        "fact_affordability", "apciq_geography_key", "dim_geography", "geography_key",
        "bridge_census_tract_apciq_sector.apciq_geography_key -> dim_geography.geography_key",
    ),
]

# What each edge MEANS, in words, because the constraint name is what drawDB
# prints next to the line and a reader gets about two seconds to understand it.
# A generated name such as fk_fact_affordability_census_tract_geography_key
# restates the columns the arrow already shows, and says nothing else.
#
# Keyed by (child table, child column). An edge with no sentence here falls back
# to the technical name -- so a relationship added later shows up looking raw,
# which is a visible prompt to name it rather than a silent omission.
EDGE_LABELS = {
    ("dim_geography", "parent_geography_key"): "geography_nests_in_its_parent",
    ("bridge_apciq_sector_geography", "apciq_geography_key"): "bridge_names_an_apciq_sector",
    ("bridge_apciq_sector_geography", "admin_geography_key"): "bridge_names_an_admin_entity",
    ("bridge_census_tract_apciq_sector", "census_tract_geography_key"): "bridge_names_a_census_tract",
    ("bridge_census_tract_apciq_sector", "apciq_geography_key"): "tract_sits_in_an_apciq_sector",
    ("fact_market", "quarter_start_date"): "market_is_dated_by_quarter",
    ("fact_market", "geography_key"): "market_is_measured_in_a_sector",
    ("fact_market", "property_type_code"): "market_is_split_by_property_type",
    ("fact_market_trailing_12m", "period_end_date"): "trailing_12m_ends_on_a_date",
    ("fact_market_trailing_12m", "geography_key"): "trailing_12m_is_measured_in_a_sector",
    ("fact_market_trailing_12m", "property_type_code"): "trailing_12m_is_split_by_property_type",
    ("fact_mortgage_scenario", "mortgage_scenario_key"): "one_scenario_per_market_row",
    ("fact_affordability", "property_type_code"): "affordability_is_split_by_property_type",
    ("fact_affordability", "household_profile_code"): "affordability_is_split_by_household",
    ("fact_affordability", "census_tract_geography_key"): "affordability_is_measured_in_a_tract",
    ("fact_mortgage_scenario", "quarter_start_date"): "scenario_is_dated_by_quarter",
    ("fact_mortgage_scenario", "geography_key"): "scenario_is_measured_in_a_sector",
    ("fact_mortgage_scenario", "property_type_code"): "scenario_is_split_by_property_type",
    ("fact_affordability", "quarter_start_date"): "affordability_is_dated_by_quarter",
    ("fact_affordability", "apciq_geography_key"): "affordability_borrows_a_sector_price",
}

# drawDB parses a PostgreSQL subset. PostGIS types are not in it, and a type it
# cannot read costs the whole import. The real type is stated in the header
# comment instead of being smuggled into a column definition.
TYPE_SUBSTITUTIONS = {"geometry": "TEXT", "geography": "TEXT"}


def constraint_name(prefix: str, child: str, col: str) -> str:
    """tested_market_is_dated_by_quarter, or the raw name if unnamed."""
    return f"{prefix}_{EDGE_LABELS.get((child, col), f'{child}__{col}')}"


def load_dbt_declarations() -> tuple[dict, list, dict]:
    """Read the dbt schema YAMLs.

    Returns three things, all keyed by model name:
      keys      -- columns declared both `unique` and `not_null`. dbt has no
                   PRIMARY KEY concept; those two tests together ARE the
                   declaration. Note that several columns of the same table can
                   carry them: that is several INDEPENDENT unique constraints,
                   never one composite key -- reading it as composite is what
                   the first version of this script got wrong, and PostgreSQL
                   rejected the result.
      edges     -- every `relationships` test, as a tuple.
      not_nulls -- columns declared `not_null`, used by --keys-only.
    """
    keys: dict[str, list[str]] = {}
    edges: list[tuple[str, str, str, str]] = []
    not_nulls: dict[str, set[str]] = {}

    for path in sorted(DBT_MODELS.rglob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not doc or "models" not in doc:
            continue
        for model in doc["models"] or []:
            name = model["name"]
            for column in model.get("columns") or []:
                col = column["name"]
                tests = column.get("data_tests") or []
                plain = {t for t in tests if isinstance(t, str)}
                if "not_null" in plain:
                    not_nulls.setdefault(name, set()).add(col)
                if {"unique", "not_null"} <= plain:
                    keys.setdefault(name, []).append(col)
                for test in tests:
                    if not isinstance(test, dict) or "relationships" not in test:
                        continue
                    body = test["relationships"]
                    args = body.get("arguments", body)
                    match = REF_PATTERN.search(str(args.get("to", "")))
                    if match:
                        edges.append((name, col, match.group(1), args["field"]))
    return keys, edges, not_nulls


def load_catalog(schemas: list[str]) -> dict[str, list[tuple[str, str, bool]]]:
    """Read columns and types from the live database, in declaration order."""
    catalog: dict[str, list[tuple[str, str, bool]]] = {}
    query = """
        select c.table_name, c.column_name, c.data_type, c.udt_name,
               c.character_maximum_length, c.numeric_precision, c.numeric_scale,
               c.is_nullable
        from information_schema.columns c
        join information_schema.tables t
          on t.table_schema = c.table_schema and t.table_name = c.table_name
        where c.table_schema = any(%s)
          and t.table_type in ('BASE TABLE', 'VIEW')
        order by c.table_name, c.ordinal_position;
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, (schemas,))
        for row in cur.fetchall():
            table, column, data_type, udt, charlen, precision, scale, nullable = row
            catalog.setdefault(table, []).append(
                (column, sql_type(data_type, udt, charlen, precision, scale), nullable == "NO")
            )
        conn.rollback()
    return catalog


def sql_type(data_type: str, udt: str, charlen, precision, scale) -> str:
    """Render a portable type name drawDB can parse."""
    if udt in TYPE_SUBSTITUTIONS:
        return TYPE_SUBSTITUTIONS[udt]
    if data_type == "character varying":
        return f"VARCHAR({charlen})" if charlen else "VARCHAR"
    if data_type == "numeric":
        return f"NUMERIC({precision},{scale})" if precision is not None else "NUMERIC"
    if data_type == "timestamp with time zone":
        return "TIMESTAMP"
    if data_type == "double precision":
        return "DOUBLE PRECISION"
    return data_type.upper()


def sort_tables(names: list[str]) -> list[str]:
    return sorted(names, key=lambda n: (TABLE_ORDER.index(n) if n in TABLE_ORDER else len(TABLE_ORDER), n))


def build_ddl(catalog, keys, edges, not_nulls, keys_only: bool, star_only: bool, tested_only: bool) -> tuple[str, list, list]:
    tables = sort_tables(list(catalog))
    in_scope = set(tables)

    tested = [e for e in edges if e[0] in in_scope and e[2] in in_scope]
    dropped = [e for e in edges if e[0] in in_scope and e[2] not in in_scope]
    derived = [d for d in DERIVED_EDGES if d[0] in in_scope and d[2] in in_scope]
    # --tested-only draws nothing the build does not assert. It is the honest
    # picture: five fewer lines, and every remaining one is guaranteed.
    if tested_only:
        derived = []

    # --star drops every table no edge touches: in marts that is the seven
    # parameter seeds, which carry no key and would float as unconnected boxes.
    # The rule is "nothing points at it and it points at nothing", not a
    # hand-picked list, so a seed that ever gains a relationship comes back in.
    if star_only:
        connected = {t for e in tested for t in (e[0], e[2])}
        connected |= {t for d in derived for t in (d[0], d[2])}
        tables = [t for t in tables if t in connected]
        in_scope = set(tables)

    # Columns that carry structure. --keys-only keeps exactly these, so the
    # filter is a rule anyone can re-apply, not a hand-picked shortlist.
    structural: dict[str, set[str]] = {t: set() for t in tables}
    for table, cols in keys.items():
        if table in structural:
            structural[table].update(cols)
    for child, col, parent, field in tested:
        structural[child].add(col)
        structural[parent].add(field)
    for child, col, parent, field, _ in derived:
        structural[child].add(col)
        structural[parent].add(field)

    lines = [
        "-- Montreal Housing Intelligence -- analytical layer",
        "-- GENERATED by scripts/generate_erd.py. Do not edit by hand:",
        "-- re-run the script instead, or the diagram stops matching the database.",
        "--",
        "-- Columns and types come from information_schema on the live database.",
        "-- Primary keys are the columns dbt declares both unique and not_null.",
        "-- tested_*  : asserted by a dbt relationships test on every build.",
        "-- derived_* : real edge, asserted one table upstream, and Power BI needs it.",
        "--",
        "-- dim_geography.geometry is PostGIS geometry(MultiPolygon, 4326),",
        "-- rendered as TEXT because drawDB does not parse PostGIS types.",
        "",
    ]

    # Which (table, column) pairs are pointed at by an edge. The primary key is
    # the one a relationship actually joins on; the other unique columns become
    # UNIQUE constraints, which is what they are. Falling back to the first
    # declared column only matters for tables nothing points at.
    inbound = {(p, f) for _, _, p, f in tested} | {(p, f) for _, _, p, f, _ in derived}

    for table in tables:
        columns = catalog[table]
        if keys_only:
            keep = structural[table] | not_nulls.get(table, set())
            columns = [c for c in columns if c[0] in keep] or columns
        candidates = keys.get(table, [])
        pk = next((c for c in candidates if (table, c) in inbound), candidates[0] if candidates else None)
        body = []
        width = max(len(c[0]) for c in columns)
        for name, type_name, db_not_null in columns:
            null_clause = " NOT NULL" if (db_not_null or name in not_nulls.get(table, set())) else ""
            body.append(f"    {name.ljust(width)} {type_name}{null_clause}")
        if pk:
            body.append(f"    PRIMARY KEY ({pk})")
        for other in candidates:
            if other != pk:
                body.append(f"    UNIQUE ({other})")
        lines.append(f"CREATE TABLE {table} (")
        lines.append(",\n".join(body))
        lines.append(");")
        lines.append("")

    lines.append("-- Referential integrity, recovered from the dbt relationships tests.")
    lines.append("")
    for child, col, parent, field in tested:
        lines.append(
            f"ALTER TABLE {child} ADD CONSTRAINT {constraint_name('tested', child, col)} "
            f"FOREIGN KEY ({col}) REFERENCES {parent}({field});"
        )
    if derived:
        lines.append("")
        lines.append("-- Star-schema edges Power BI needs, asserted one table upstream.")
        lines.append("")
        for child, col, parent, field, _ in derived:
            lines.append(
                f"ALTER TABLE {child} ADD CONSTRAINT {constraint_name('derived', child, col)} "
                f"FOREIGN KEY ({col}) REFERENCES {parent}({field});"
            )
    lines.append("")
    return "\n".join(lines), tested + [(c, k, p, f) for c, k, p, f, _ in derived], dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layer", choices=["marts", "all"], default="marts",
        help="marts (default) draws the star schema; all adds raw and staging.",
    )
    parser.add_argument(
        "--keys-only", action="store_true",
        help="Keep only columns carrying a key, a relationship or a not_null test.",
    )
    parser.add_argument(
        "--star", action="store_true",
        help="Drop every table no relationship touches (the parameter seeds).",
    )
    parser.add_argument(
        "--tested-only", action="store_true",
        help="Draw only edges a dbt test asserts. Five fewer lines, nothing unproven.",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    schemas = ["marts"] if args.layer == "marts" else ["marts", "staging", "raw"]
    keys, edges, not_nulls = load_dbt_declarations()
    catalog = load_catalog(schemas)
    if not catalog:
        print("No table found. Is the SSH tunnel open? bash scripts/tunnel-start.sh")
        return 1

    ddl, drawn, dropped = build_ddl(catalog, keys, edges, not_nulls, args.keys_only, args.star, args.tested_only)

    suffix = ("-star" if args.star else "") + ("-keys" if args.keys_only else "") + ("-tested" if args.tested_only else "")
    out = args.out or DEFAULT_OUT / f"mhi-{args.layer}{suffix}.sql"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ddl, encoding="utf-8")

    print(f"Wrote {out.relative_to(REPO_ROOT)}")
    print(f"  tables      : {ddl.count(chr(10) + chr(10) + 'CREATE TABLE') + ddl.startswith('CREATE TABLE')} drawn (out of {len(catalog)} in scope)")
    print(f"  relationships: {len(drawn)} drawn")
    for child, col, parent, field in dropped:
        print(f"  NOT drawn (target outside the {args.layer} layer): {child}.{col} -> {parent}.{field}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
