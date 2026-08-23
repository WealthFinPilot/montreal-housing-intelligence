"""Fetch and archive the quarterly PDFs. HTTP only -- no database here.

WHY THE PDFs ARE ARCHIVED RATHER THAN STREAMED
----------------------------------------------
docs/data-sources.md puts APCIQ at automation difficulty 4/5 and names the
reason: it is the only verified source of realised-market statistics, and it
is a quarterly PDF whose URL pattern and page layout can change without
notice. Principle 41.6 of the brief protects the pipeline against losing
Apify; nothing protects it against losing APCIQ.

So the first fetch of a quarter writes the file to disk and every later run
reads that copy. If the site reorganises tomorrow, the 29 quarters already on
disk still parse. About 200 MB, outside git -- data/ is gitignored, and the
licence forbids redistributing the content anyway.

A partly written file would be worse than no file: it would look cached and
fail to parse forever. Downloads therefore land in a `.part` file and are
renamed only once complete, which on every platform this project runs on is
an atomic operation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

from ingestion.apciq.editions import Edition

# The archive is served through a redirect, and the host answers 302 to HEAD
# for URLs that do not exist. Following redirects is mandatory, not optional.
REQUEST_TIMEOUT = (10, 120)  # connect, read -- these files reach 9.5 MB
CHUNK_BYTES = 1 << 16

# Below this, the response is not a Baromètre. The smallest edition seen is
# 5.7 MB; an error page would be a few kilobytes.
MIN_PLAUSIBLE_BYTES = 1_000_000


class EditionNotPublished(Exception):
    """The URL answered 404. Expected at the tail of the series, nowhere else."""


class SuspiciousDownload(Exception):
    """The response arrived but does not look like a Baromètre PDF."""


@dataclass(frozen=True)
class ArchiveEntry:
    edition: Edition
    path: Path | None
    status: str          # 'cached' | 'downloaded' | 'not-published'
    size_bytes: int = 0

    def __str__(self) -> str:
        if self.path is None:
            return f"{self.edition}  not published"
        return f"{self.edition}  {self.status:<10} {self.size_bytes / 1e6:5.1f} MB"


def archive_path(edition: Edition, archive_dir: Path) -> Path:
    return archive_dir / edition.filename


def fetch_edition(
    edition: Edition,
    destination: Path,
    *,
    session: requests.Session | None = None,
) -> int:
    """Download one edition to `destination`. Returns the byte count.

    Raises EditionNotPublished on 404, SuspiciousDownload if what came back is
    too small or is not a PDF.
    """
    http = session or requests.Session()
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    with http.get(
        edition.url, stream=True, allow_redirects=True, timeout=REQUEST_TIMEOUT
    ) as response:
        if response.status_code == 404:
            raise EditionNotPublished(f"{edition}: 404 at {edition.url}")
        response.raise_for_status()

        written = 0
        with partial.open("wb") as handle:
            for chunk in response.iter_content(CHUNK_BYTES):
                handle.write(chunk)
                written += len(chunk)

    try:
        if written < MIN_PLAUSIBLE_BYTES:
            raise SuspiciousDownload(
                f"{edition}: {written} bytes is too small to be a Baromètre "
                f"(smallest seen: 5.7 MB). The URL probably answered with an "
                f"error page carrying a 200."
            )
        with partial.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise SuspiciousDownload(f"{edition}: response is not a PDF")
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    os.replace(partial, destination)
    return written


def ensure_archived(
    editions: list[Edition],
    archive_dir: Path,
    *,
    session: requests.Session | None = None,
    force: bool = False,
    on_progress=None,
) -> list[ArchiveEntry]:
    """Make sure every edition is on disk, downloading only what is missing.

    Tolerates 404s, then checks where they fell -- see check_no_hole().
    """
    http = session or requests.Session()
    entries: list[ArchiveEntry] = []

    for edition in editions:
        target = archive_path(edition, archive_dir)
        if target.exists() and target.stat().st_size >= MIN_PLAUSIBLE_BYTES and not force:
            entry = ArchiveEntry(edition, target, "cached", target.stat().st_size)
        else:
            try:
                size = fetch_edition(edition, target, session=http)
                entry = ArchiveEntry(edition, target, "downloaded", size)
            except EditionNotPublished:
                entry = ArchiveEntry(edition, None, "not-published")
        entries.append(entry)
        if on_progress is not None:
            on_progress(entry)

    return entries


def check_no_hole(entries: list[ArchiveEntry]) -> None:
    """A missing quarter is normal at the end of the list and nowhere else.

    APCIQ publishes a few weeks after the quarter closes, so the newest one or
    two candidates legitimately answer 404. A 404 followed by a file that does
    exist means the archive lost a quarter, or the URL pattern changed for
    that year -- either way the series has a hole, and a hole in a quarterly
    series is exactly the kind of thing that produces a plausible, wrong
    trend line. Refuse instead.
    """
    missing = [e.edition for e in entries if e.path is None]
    if not missing:
        return

    last_present = max(
        (i for i, e in enumerate(entries) if e.path is not None), default=-1
    )
    holes = [e.edition for i, e in enumerate(entries) if e.path is None and i < last_present]
    if holes:
        raise EditionNotPublished(
            "gap inside the archive: "
            + ", ".join(str(edition) for edition in holes)
            + ". The series is not continuous, so nothing was loaded."
        )
