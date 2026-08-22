"""Shared test setup.

Two families of tests live in this folder:

  * unit tests      -- pure functions, no network, no database. They must run
                       in under a second, offline, on any machine.
  * database tests  -- marked @pytest.mark.db. They need the SSH tunnel open.
                       Every one of them runs inside a transaction that is
                       ROLLED BACK afterwards, so running the test suite never
                       leaves a trace in the database.

If the tunnel is closed, the database tests are skipped with an explicit
message rather than failing: a closed tunnel is a missing precondition, not a
broken pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def valet_payload() -> dict:
    """A real Bank of Canada Valet response, captured on 2026-08-22.

    Two series with different frequencies (daily and weekly) over the same
    fortnight, which is exactly the awkward case the parser has to get right.
    """
    return json.loads((FIXTURES / "valet_two_series.json").read_text(encoding="utf-8"))


@pytest.fixture
def db_connection():
    """A database connection whose work is always rolled back.

    autocommit stays off and no commit is ever issued, so whatever a test
    writes disappears when the connection closes. That is what makes it safe
    to test against the real tables instead of a fake copy.
    """
    import psycopg

    from src import db

    try:
        conn = db.connect()
    except psycopg.OperationalError as exc:
        pytest.skip(
            f"database unreachable ({db.describe_target()}): {exc}\n"
            "Open the tunnel first:  bash scripts/tunnel-start.sh"
        )

    try:
        yield conn
        conn.rollback()
    finally:
        conn.close()
