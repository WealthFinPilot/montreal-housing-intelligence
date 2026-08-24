"""HTTP for the Statistics Canada sources. No database, no parsing.

Two different ways in, because Statistics Canada publishes these files two
different ways.

    the income table   a web service that hands back a URL when asked
    the other two      an HTML form that answers 302 with the path in the
                       Location header

Both are resolved on every run rather than hard-coded. The reason is the one
already recorded for the Données Montréal resource UUIDs: a path that is
correct today is a guess tomorrow, and a guess that happens to return 200 is
the expensive kind of wrong.

WHY THE REDIRECT IS READ RATHER THAN FOLLOWED
---------------------------------------------
Following it lands on an intermediate page that answers 411 to a body-less
POST. The Location header already names the file, so the redirect is read for
its `loc` parameter and the file fetched directly with a plain GET.
"""

from __future__ import annotations

import posixpath
from urllib.parse import parse_qs, urlparse

import requests

from ingestion.statcan.datasets import WWW12, Dataset

TIMEOUT = 120

# The files are 6 to 13 MB compressed. Kept in memory rather than written to
# disk: parse.py streams the CSV straight out of the archive, so the 298 MB
# unzipped attribute file never exists anywhere as a file. Same lesson as the
# MAMH roll -- see the header of ingestion/mamh_roll/extract_roll.py.
MAX_REASONABLE_BYTES = 200 * 1024 * 1024


class DownloadError(RuntimeError):
    """The source did not answer the way this module requires."""


def _session(session: requests.Session | None) -> requests.Session:
    return session if session is not None else requests.Session()


def resolve_url(dataset: Dataset, *, session: requests.Session | None = None) -> str:
    """Ask the source where the file is. Returns an absolute URL."""
    if dataset.wds_url:
        return _resolve_through_wds(dataset, session=_session(session))
    if dataset.form_url:
        return _resolve_through_form(dataset, session=_session(session))
    raise DownloadError(f"{dataset.key}: no way to resolve a URL is declared")


def _resolve_through_wds(dataset: Dataset, *, session: requests.Session) -> str:
    response = session.get(dataset.wds_url, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "SUCCESS":
        raise DownloadError(
            f"{dataset.key}: the web service answered status "
            f"{payload.get('status')!r} instead of SUCCESS"
        )
    url = payload.get("object")
    if not url:
        raise DownloadError(f"{dataset.key}: the web service returned no URL")
    return url


def _resolve_through_form(dataset: Dataset, *, session: requests.Session) -> str:
    """Post the download form and read the file path out of the redirect."""
    response = session.post(
        dataset.form_url,
        data=dataset.form_fields,
        allow_redirects=False,
        timeout=TIMEOUT,
    )
    if response.status_code not in (301, 302, 303, 307, 308):
        raise DownloadError(
            f"{dataset.key}: the form answered HTTP {response.status_code} "
            "instead of a redirect. The form fields have probably changed -- "
            "open the page and read them again rather than guessing a URL."
        )

    location = response.headers.get("Location", "")
    candidates = parse_qs(urlparse(location).query).get("loc")
    if not candidates:
        raise DownloadError(
            f"{dataset.key}: the redirect carried no `loc` parameter. "
            f"Location was: {location[:200]}"
        )

    path = candidates[0]
    if path.startswith("//"):
        return "https:" + path
    if path.startswith("/"):
        return WWW12 + path
    return path


def fetch(dataset: Dataset, *, session: requests.Session | None = None) -> tuple[bytes, str]:
    """Resolve, check the filename, download. Returns the bytes and the URL.

    The filename check is the point of this function. A boundary file for the
    wrong geography, or a table for the wrong year, downloads with HTTP 200,
    parses without complaint and produces rows that look entirely normal. The
    only cheap moment to catch that is here.
    """
    session = _session(session)
    url = resolve_url(dataset, session=session)

    if dataset.expected_filename:
        served = posixpath.basename(urlparse(url).path)
        # The income service serves a zip whose name is the table id; the
        # expected filename names the CSV inside it. Accept either, and let
        # parse.py check the member name.
        expected_stem = dataset.expected_filename.rsplit(".", 1)[0]
        if expected_stem not in served:
            raise DownloadError(
                f"{dataset.key}: the source served {served!r}, which does not "
                f"look like {dataset.expected_filename!r}. Refusing to load a "
                "file this pipeline was not written for."
            )

    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.content

    if len(payload) > MAX_REASONABLE_BYTES:
        raise DownloadError(
            f"{dataset.key}: {len(payload):,} bytes is far larger than this "
            "source has ever been. Check what changed before loading it."
        )
    return payload, url
