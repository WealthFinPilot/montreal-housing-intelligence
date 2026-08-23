"""What the migration runner must guarantee, written before the runner exists.

Three promises are locked here:

  1. Files run in filename order, always. Table B cannot be created before
     table A because someone renamed a file.
  2. A file that already ran does not run again.
  3. A file that already ran and has since been EDITED is reported as drift,
     not silently ignored. Editing an applied migration means the database on
     the VPS and the database a reader creates from a fresh clone no longer
     match -- and nothing else in the project would notice.

The first three tests need no database: `plan()` is a pure function that
compares two lists. That is deliberate -- the interesting logic is the one
that must be testable offline.
"""

from __future__ import annotations

import pytest

from src import migrations


def _migration(name: str, sql: str) -> migrations.Migration:
    return migrations.Migration(
        filename=name, sql=sql, checksum=migrations.checksum_of(sql)
    )


# ---------------------------------------------------------------------------
# Pure logic: what should run, given what already ran.
# ---------------------------------------------------------------------------


def test_everything_is_pending_on_an_empty_database():
    available = [_migration("01_a.sql", "CREATE SCHEMA a;"),
                 _migration("02_b.sql", "CREATE TABLE b();")]

    outcome = migrations.plan(available, applied={})

    assert [m.filename for m in outcome.pending] == ["01_a.sql", "02_b.sql"]
    assert outcome.drifted == []


def test_an_already_applied_file_is_not_replayed():
    first = _migration("01_a.sql", "CREATE SCHEMA a;")
    second = _migration("02_b.sql", "CREATE TABLE b();")

    outcome = migrations.plan([first, second], applied={"01_a.sql": first.checksum})

    assert [m.filename for m in outcome.pending] == ["02_b.sql"]
    assert outcome.drifted == []


def test_editing_an_applied_file_is_reported_as_drift():
    """The whole point of the checksum column.

    The registry says 01_a.sql ran with one content; the repository now holds
    a different one. Replaying it would not fix the database, and staying
    quiet would leave two databases that disagree. So: report it.
    """
    edited = _migration("01_a.sql", "CREATE SCHEMA a_renamed;")
    stale_checksum = migrations.checksum_of("CREATE SCHEMA a;")

    outcome = migrations.plan([edited], applied={"01_a.sql": stale_checksum})

    assert outcome.pending == []
    assert outcome.drifted == ["01_a.sql"]


def test_files_are_ordered_by_filename_not_by_discovery_order():
    out_of_order = [_migration("10_late.sql", "SELECT 10;"),
                    _migration("02_early.sql", "SELECT 2;")]

    outcome = migrations.plan(out_of_order, applied={})

    assert [m.filename for m in outcome.pending] == ["02_early.sql", "10_late.sql"]


# ---------------------------------------------------------------------------
# The real files in this repository.
# ---------------------------------------------------------------------------


def test_the_repository_migrations_are_discovered_in_order():
    found = migrations.discover()

    assert found, "sql/bootstrap/ holds no .sql file"
    assert [m.filename for m in found] == sorted(m.filename for m in found)
    # Every migration must be replayable: the runner reapplies the whole set
    # on a database Docker already initialised, so a bare CREATE would fail.
    for m in found:
        assert "IF NOT EXISTS" in m.sql.upper(), (
            f"{m.filename} is not written to be replayable -- see the header "
            "rule in sql/bootstrap/00_schema_migration.sql"
        )


# ---------------------------------------------------------------------------
# Against the real database, inside a transaction that is rolled back.
# ---------------------------------------------------------------------------


@pytest.mark.db
def test_applying_twice_leaves_nothing_to_do_the_second_time(db_connection):
    """Idempotence, proven rather than asserted in a comment."""
    first_pass = migrations.run(db_connection)
    second_pass = migrations.run(db_connection)

    assert second_pass.pending == [], (
        "second run still wants to apply "
        f"{[m.filename for m in second_pass.pending]}"
    )
    assert second_pass.drifted == []
    # Nothing is committed: the fixture rolls back, so the registry rows
    # written above disappear with the connection.
    assert first_pass.applied_count >= 0


@pytest.mark.db
def test_the_registry_records_every_file_it_applied(db_connection):
    migrations.run(db_connection)

    recorded = migrations.read_registry(db_connection)
    for m in migrations.discover():
        assert m.filename in recorded, f"{m.filename} ran but was not recorded"
        assert recorded[m.filename] == m.checksum
