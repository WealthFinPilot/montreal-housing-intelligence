"""Refuse to publish a term that belongs to private context, not to the project.

This repository documents a data project and nothing else. Personal context
and working notes stay on the author's machine, and a rule that lives only in
someone's memory is broken by the first forgotten comment. So the rule is
checked, like a secret is.

The list of terms is itself private -- publishing it would publish exactly
what it protects -- so it is never tracked. It lives in .git/info/, a folder
git never commits, never puts in an archive and never clones. Same reasoning
as .env, one level stricter: there is not even an ignore rule to read.

Two modes:

  files      (default) every file git would carry: its PATH, and its content
             when it is text. Binary files are counted, never skipped in
             silence -- section 7 of check-secrets.sh names them.
  --history  every commit reachable from the given revisions (default --all):
             its message, and its patch, which carries every path and every
             line that was ever added. Run it on a history before publishing
             it, not only on the tree: a term removed today is still in the
             commit that added it.

One exception: Co-Authored-By trailer lines of a commit message are
attribution, kept by decision on 2026-09-16, and are not searched.

Terms are matched as whole words, case-insensitively and accent-exactly, after
Unicode normalisation -- "e" + combining accent and "é" are the same word.

Exit codes:  0 = clean,  1 = a term was found (or the self-check failed),
             2 = no term list, so the check did NOT run.

Usage:
    python scripts/check_publication_terms.py
    python scripts/check_publication_terms.py --history [REV ...]
    python scripts/check_publication_terms.py --repo PATH --history --all
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DENYLIST_NAME = "info/publication-denylist"

# A commit message is framed by two control characters that never appear in
# text, so a message that happens to contain "diff --git" cannot be mistaken
# for the start of its patch.
COMMIT_MARK = "\x1eCOMMIT "
MESSAGE_END = "\x1eEND"

TRAILER = re.compile(r"^\s*co-authored-by:", re.IGNORECASE)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    ).stdout


def denylist_path(repo: Path) -> Path:
    return repo / git(repo, "rev-parse", "--git-path", DENYLIST_NAME).strip()


def normalise(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def load_terms(path: Path) -> list[str]:
    """One term per line; blank lines and lines starting with # are ignored."""
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(normalise(line))
    return terms


def compile_terms(terms: list[str]) -> re.Pattern[str]:
    # Whole words, not substrings: a term must not fire inside a longer word.
    # \w is Unicode-aware, so an accented letter counts as part of a word.
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")


def find_terms(pattern: re.Pattern[str], text: str) -> list[str]:
    return pattern.findall(normalise(text))


# --------------------------------------------------------------------------
# Files mode
# --------------------------------------------------------------------------


def candidate_files(repo: Path) -> list[str]:
    # -z: without it git quotes a non-ASCII path, and the quoted name opens no
    # file. Repaired in the other guards on 2026-09-15; not repeated here.
    listed = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return [p for p in listed.split("\0") if p]


def scan_files(repo: Path, pattern: re.Pattern[str]) -> tuple[list[tuple[str, int, str]], int, int]:
    hits: list[tuple[str, int, str]] = []
    binary = 0
    files = candidate_files(repo)
    for rel in files:
        for term in find_terms(pattern, rel):
            hits.append((rel, 0, term))
        path = repo / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8000]:
            binary += 1
            continue
        text = data.decode("utf-8", errors="replace")
        # split("\n") so a line number means what an editor shows: splitlines
        # also breaks on form feeds and Unicode separators, and drifts.
        for lineno, line in enumerate(text.split("\n"), start=1):
            for term in find_terms(pattern, line):
                hits.append((rel, lineno, term))
    return hits, len(files), binary


# --------------------------------------------------------------------------
# History mode
# --------------------------------------------------------------------------


def scan_log(pattern: re.Pattern[str], log: str) -> dict[str, dict[str, set[str]]]:
    """{commit: {"message": terms, "content": terms}} for every commit with a hit.

    `log` is the output of git log -p with the COMMIT_MARK / MESSAGE_END framing.
    """
    found: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    sha = None
    in_message = False
    # split("\n"), never splitlines(): splitlines also breaks on \x1e, the very
    # character that frames a message, so no commit was ever recognised and
    # every history scanned clean. Caught by the tests before the first run.
    for line in log.split("\n"):
        if line.startswith(COMMIT_MARK):
            sha = line[len(COMMIT_MARK):].strip()
            in_message = True
            continue
        if line == MESSAGE_END:
            in_message = False
            continue
        if sha is None:
            continue
        if in_message:
            if TRAILER.match(line):
                continue
            where = "message"
        else:
            where = "content"
        for term in find_terms(pattern, line):
            found[sha][where].add(term)
    return found


def read_log(repo: Path, revisions: list[str]) -> str:
    return git(
        repo, "log", "-p", "--no-color", "--no-ext-diff",
        f"--format={COMMIT_MARK}%H%n%B{MESSAGE_END}", *revisions,
    )


# --------------------------------------------------------------------------


def self_check(pattern: re.Pattern[str], terms: list[str]) -> bool:
    """A checker that always answers clean proves nothing.

    Plant the first term inside an ordinary sentence, once as written and once
    in upper case with its accents decomposed, and require both to be found.
    """
    probe = terms[0]
    planted = f"An ordinary line that mentions {probe} in passing."
    shouted = unicodedata.normalize("NFD", f"ALSO ({probe.upper()}).")
    return bool(find_terms(pattern, planted)) and bool(find_terms(pattern, shouted))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refuse to publish a term that belongs to private context."
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--history", nargs="*", metavar="REV")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    # A Windows console defaults to cp1252 and prints an accented term as "?",
    # which makes a report about words unreadable exactly where it matters.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    listing = denylist_path(repo)
    if not listing.is_file():
        print(f"  SKIP  no term list at {listing}")
        print("        The publication check did NOT run. A clean verdict from the")
        print("        other sections says nothing about private context.")
        return 2
    terms = load_terms(listing)
    if not terms:
        print(f"  SKIP  the term list at {listing} is empty -- nothing was checked")
        return 2
    pattern = compile_terms(terms)

    status = 0
    if args.history is None:
        hits, total, binary = scan_files(repo, pattern)
        print(f"  ..    {len(terms)} private terms; {total} candidate files, "
              f"{total - binary} searched as text, {binary} binary")
        if hits:
            by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
            for rel, lineno, term in hits:
                by_file[rel].append((lineno, term))
            print(f"  FAIL  {len(hits)} private term(s) in {len(by_file)} file(s):")
            for rel in sorted(by_file):
                places = ", ".join(
                    f"{'path' if n == 0 else n}:{t}" for n, t in by_file[rel][:6]
                )
                more = len(by_file[rel]) - 6
                print(f"          {rel}  {places}" + (f"  (+{more})" if more > 0 else ""))
            status = 1
        else:
            print("  OK    no private term in any candidate file, path or content")
    else:
        revisions = args.history or ["--all"]
        found = scan_log(pattern, read_log(repo, revisions))
        count = int(git(repo, "rev-list", "--count", *revisions).strip() or 0)
        print(f"  ..    {len(terms)} private terms; {count} commits reachable from "
              f"{' '.join(revisions)}")
        if found:
            in_messages = sum(1 for f in found.values() if f.get("message"))
            in_content = sum(1 for f in found.values() if f.get("content"))
            print(f"  FAIL  {len(found)} commit(s) carry a private term -- "
                  f"{in_messages} in the message, {in_content} in the content:")
            for sha, where in found.items():
                parts = [f"{kind}: {', '.join(sorted(t))}" for kind, t in where.items()]
                print(f"          {sha[:7]}  " + " | ".join(parts))
            status = 1
        else:
            print("  OK    no private term in any message, path or patch of that history")

    if self_check(pattern, terms):
        print("  OK    self-check: a planted term is found, plain and shouted")
    else:
        print("  FAIL  self-check: a planted term was NOT found -- every OK above is worthless")
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
