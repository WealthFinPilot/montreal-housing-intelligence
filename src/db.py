"""How this project reaches PostgreSQL.

The database runs in a container on the VPS and listens on that server's
loopback interface only. It is therefore unreachable from anywhere until an
SSH tunnel is opened:

    bash scripts/tunnel-start.sh

which makes 127.0.0.1:15432 on this laptop come out at 127.0.0.1:5432 on the
server. That is why the default port below is 15432 and not 5432: on this
machine, 15432 means "the VPS, through the tunnel".

Credentials come from .env and never from the source code. Real environment
variables win over .env, so the same code runs unchanged on the server itself
(where MHI_DB_PORT would be 5432 and no tunnel exists).
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

# Local end of the SSH tunnel. Override with MHI_DB_HOST / MHI_DB_PORT.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 15432

# Deliberately NOT reused: POSTGRES_PORT in .env is the port the container
# publishes on the SERVER's loopback. It answers a different question from
# "which port does a client on this machine dial", and conflating the two
# would break the moment either side moves.
_CLIENT_PORT_VAR = "MHI_DB_PORT"


class MissingCredentialError(RuntimeError):
    """A required connection setting is absent from the environment and .env."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingCredentialError(
            f"{name} is not set. Expected it in {ENV_FILE} or in the environment."
        )
    return value


def connection_kwargs() -> dict:
    """Everything psycopg needs to connect, read from the environment."""
    # override=False: a real environment variable beats the .env file. That is
    # what lets the VPS, a CI job or a one-off test point somewhere else
    # without editing a tracked file.
    load_dotenv(ENV_FILE, override=False)
    return {
        "host": os.environ.get("MHI_DB_HOST", DEFAULT_HOST),
        "port": int(os.environ.get(_CLIENT_PORT_VAR, DEFAULT_PORT)),
        "dbname": _require("POSTGRES_DB"),
        "user": _require("POSTGRES_USER"),
        "password": _require("POSTGRES_PASSWORD"),
        "connect_timeout": 10,
        # Shows up in pg_stat_activity, so a stuck session on the server can be
        # traced back to this project rather than to "some python".
        "application_name": "mhi_ingestion",
    }


def describe_target() -> str:
    """Where we are about to connect, safe to print. Never includes the password."""
    kw = connection_kwargs()
    return f"{kw['user']}@{kw['host']}:{kw['port']}/{kw['dbname']}"


def connect() -> psycopg.Connection:
    """Open a connection with autocommit OFF.

    Autocommit stays off on purpose: the caller decides when work becomes
    permanent. That is what lets the test suite run against the real tables and
    roll everything back afterwards.
    """
    return psycopg.connect(**connection_kwargs())
