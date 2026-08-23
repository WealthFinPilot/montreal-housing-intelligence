"""Applies the SQL files in sql/bootstrap/ to a database that already exists.

Read sql/bootstrap/00_schema_migration.sql first: it explains why the project
needs this at all, and states the two rules the runner enforces.

The interesting part of this module is `plan()`, and it touches no database:
it compares the files on disk with the rows in the registry and answers two
questions -- what still has to run, and what has been edited after running.
Keeping that logic pure is what lets the test suite cover it offline, in
milliseconds, without a tunnel.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "sql" / "bootstrap"

# Applied before anything is read, because it creates the registry the rest of
# the run depends on. Safe to reapply: like every file here, it is IF NOT EXISTS.
REGISTRY_MIGRATION = "00_schema_migration.sql"


@dataclass(frozen=True)
class Migration:
    filename: str
    sql: str
    checksum: str


@dataclass
class Plan:
    """What a run is about to do."""

    pending: list[Migration] = field(default_factory=list)
    drifted: list[str] = field(default_factory=list)


@dataclass
class Report:
    """What a run actually did."""

    pending: list[Migration] = field(default_factory=list)
    drifted: list[str] = field(default_factory=list)
    applied_count: int = 0


def checksum_of(sql: str) -> str:
    """SHA-256 of a migration's text.

    Newlines are normalised first. Git checks this repository out with CRLF on
    Windows and LF elsewhere; without this, the same file would produce two
    different checksums depending on the machine, and every run would cry
    drift for no reason.
    """
    normalised = sql.replace("\r\n", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def discover(directory: Path | None = None) -> list[Migration]:
    """Every .sql file in the folder, in filename order.

    Order comes from the numeric prefix, which is why files are named
    00_, 01_, 02_ and not by topic. Table order matters: a foreign key cannot
    point at a table that does not exist yet.
    """
    directory = directory or MIGRATIONS_DIR
    found = []
    for path in sorted(directory.glob("*.sql"), key=lambda p: p.name):
        sql = path.read_text(encoding="utf-8")
        found.append(Migration(path.name, sql, checksum_of(sql)))
    return found


def plan(available: list[Migration], applied: dict[str, str]) -> Plan:
    """Split the files into "must run" and "has been edited since it ran".

    `applied` maps filename -> checksum, straight from the registry.
    A file the registry does not know about is pending. A file it knows with a
    different checksum has been edited after the fact: it is NOT replayed,
    because replaying it would not undo whatever the old version already did.
    It is reported instead.
    """
    outcome = Plan()
    for migration in sorted(available, key=lambda m: m.filename):
        recorded = applied.get(migration.filename)
        if recorded is None:
            outcome.pending.append(migration)
        elif recorded != migration.checksum:
            outcome.drifted.append(migration.filename)
    return outcome


def read_registry(conn: psycopg.Connection) -> dict[str, str]:
    """filename -> checksum, for everything this database has already run."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename, checksum FROM public.schema_migration")
        return dict(cur.fetchall())


def apply(conn: psycopg.Connection, migration: Migration) -> None:
    """Run one migration and record it, in the same transaction.

    Both statements share a transaction on purpose: a migration that succeeds
    but is not recorded would run again on the next pass, and a migration
    recorded but not run would never happen at all. Neither half is allowed to
    land without the other.

    Committing is the caller's job -- which is what lets the test suite roll
    the whole thing back.
    """
    with conn.cursor() as cur:
        cur.execute(migration.sql)
        cur.execute(
            """
            INSERT INTO public.schema_migration (filename, checksum)
                 VALUES (%s, %s)
            ON CONFLICT (filename)
              DO UPDATE SET checksum = EXCLUDED.checksum,
                            applied_at = now()
            """,
            (migration.filename, migration.checksum),
        )


def run(conn: psycopg.Connection, directory: Path | None = None) -> Report:
    """Bring this database up to date with the repository. Does not commit."""
    available = discover(directory)

    # Chicken and egg: the registry table has to exist before the registry can
    # be read. The file that creates it is applied unconditionally, which is
    # harmless because it is replayable like all the others.
    registry_ddl = next(
        (m for m in available if m.filename == REGISTRY_MIGRATION), None
    )
    if registry_ddl is None:
        raise FileNotFoundError(
            f"{REGISTRY_MIGRATION} is missing from {directory or MIGRATIONS_DIR}. "
            "It creates the table every other migration is recorded in."
        )
    with conn.cursor() as cur:
        cur.execute(registry_ddl.sql)

    outcome = plan(available, read_registry(conn))
    for migration in outcome.pending:
        apply(conn, migration)

    return Report(
        pending=outcome.pending,
        drifted=outcome.drifted,
        applied_count=len(outcome.pending),
    )


def main() -> int:
    """Command line entry point. Run it through `bash scripts/migrate.sh`.

    The transaction is the safety mechanism here, not a convention: everything
    runs inside one, and drift causes a rollback. A run either brings the
    database fully up to date or changes nothing at all.
    """
    from src import db

    print(f"Target   : {db.describe_target()}")
    print(f"Files    : {MIGRATIONS_DIR}")

    with db.connect() as conn:
        report = run(conn)

        if report.drifted:
            conn.rollback()
            print()
            print("DRIFT -- nothing was applied.")
            for name in report.drifted:
                print(f"  {name} has changed since this database ran it.")
            print()
            print("An applied migration is history: this database already has")
            print("whatever the old version of the file did, and rerunning the")
            print("new version would not undo it. Two ways out:")
            print("  * the edit was accidental -> restore the file (git checkout)")
            print("  * the change is wanted    -> leave the applied file alone")
            print("                               and add a new numbered one")
            return 1

        conn.commit()

    if report.applied_count == 0:
        print("\nUP TO DATE -- nothing to apply.")
    else:
        print(f"\nAPPLIED {report.applied_count} migration(s):")
        for migration in report.pending:
            print(f"  {migration.filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
