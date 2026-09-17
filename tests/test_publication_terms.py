"""The guard that keeps private context out of a published repository.

`check_publication_terms.py` reads its terms from a list that is never tracked,
so these tests never use a real one: every term below is invented, and would
be pointless to publish. What they pin down is the matching -- whole words,
any case, any Unicode form -- and the one place the history scan deliberately
looks away.

No database and no real repository needed.
"""

from __future__ import annotations

import importlib.util
import subprocess
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_publication_terms", REPO_ROOT / "scripts" / "check_publication_terms.py"
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

TERMS = [guard.normalise(t) for t in ["Zéphyrine", "Quokka Lab", "notes.md"]]
PATTERN = guard.compile_terms(TERMS)


@pytest.mark.parametrize(
    "line, why",
    [
        ("Decided by Zéphyrine on Monday.", "as written"),
        ("DECIDED BY ZÉPHYRINE.", "upper case, accent kept"),
        (unicodedata.normalize("NFD", "par Zéphyrine"), "accent as a combining mark"),
        ("(Quokka Lab)", "a two-word term inside brackets"),
        ("see notes.md, section 2", "a file name with a dot"),
    ],
)
def test_a_term_is_found_however_it_is_written(line: str, why: str) -> None:
    assert guard.find_terms(PATTERN, line), why


@pytest.mark.parametrize(
    "line, why",
    [
        ("Zéphyrines", "a longer word is a different word"),
        ("Quokka Laboratory", "the term is a prefix of the word"),
        ("mynotes.md", "the term is the tail of a longer name"),
        ("Zephyrine", "an accent is part of the spelling: list both forms"),
    ],
)
def test_a_term_does_not_fire_inside_another_word(line: str, why: str) -> None:
    assert not guard.find_terms(PATTERN, line), why


def test_comments_and_blank_lines_are_not_terms(tmp_path: Path) -> None:
    listing = tmp_path / "list"
    listing.write_text("# a comment\n\n  Zéphyrine  \n", encoding="utf-8")
    assert guard.load_terms(listing) == ["zéphyrine"]


def _log(*commits: tuple[str, str, str]) -> str:
    return "".join(
        f"{guard.COMMIT_MARK}{sha}\n{message}\n{guard.MESSAGE_END}\n{patch}\n"
        for sha, message, patch in commits
    )


def test_history_separates_message_from_content() -> None:
    log = _log(
        ("a" * 40, "Fix the loader\n\nAs Zéphyrine asked.", "+clean line"),
        ("b" * 40, "Clean message", "diff --git a/notes.md b/notes.md\n+x"),
        ("c" * 40, "Clean", "+nothing here"),
    )
    found = guard.scan_log(PATTERN, log)
    assert set(found) == {"a" * 40, "b" * 40}
    assert found["a" * 40]["message"] == {"zéphyrine"}
    assert not found["a" * 40].get("content")
    assert found["b" * 40]["content"] == {"notes.md"}


def test_the_co_authored_by_trailer_is_not_searched() -> None:
    """Attribution kept by decision; any other line of the message still is."""
    log = _log(("d" * 40, "Add tests\n\nCo-Authored-By: Quokka Lab <x@example.com>", "+x"))
    assert guard.scan_log(PATTERN, log) == {}

    log = _log(("e" * 40, "Add tests for Quokka Lab\n\nCo-Authored-By: someone", "+x"))
    assert guard.scan_log(PATTERN, log)["e" * 40]["message"] == {"quokka lab"}


def test_a_message_that_looks_like_a_patch_is_still_a_message() -> None:
    log = _log(("f" * 40, "diff --git mentioned by Zéphyrine", "+x"))
    assert guard.scan_log(PATTERN, log)["f" * 40]["message"] == {"zéphyrine"}


def test_a_real_history_is_read_through_git(tmp_path: Path) -> None:
    """End to end on a throwaway repository: a term removed from the tree is
    still found in the commit that added it -- the reason the mode exists."""
    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "test")
    (tmp_path / "a.txt").write_text("written by Zéphyrine\n", encoding="utf-8")
    run("add", "a.txt")
    run("commit", "-q", "-m", "first")
    (tmp_path / "a.txt").write_text("written anonymously\n", encoding="utf-8")
    run("commit", "-q", "-am", "second")

    found = guard.scan_log(PATTERN, guard.read_log(tmp_path, ["--all"]))
    assert len(found) == 2          # added in the first, removed in the second
    assert all(f["content"] == {"zéphyrine"} for f in found.values())


def test_no_term_list_means_the_check_did_not_run(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert guard.main(["--repo", str(tmp_path)]) == 2


def test_the_self_check_fails_when_matching_is_broken(monkeypatch) -> None:
    monkeypatch.setattr(guard, "find_terms", lambda pattern, text: [])
    assert not guard.self_check(PATTERN, TERMS)


@pytest.mark.parametrize("code", [0, 2])
def test_check_secrets_lists_every_non_failure_exit_code(code: int) -> None:
    """An unlisted code falls into the `*` failure branch of check-secrets.sh."""
    script = (REPO_ROOT / "scripts" / "check-secrets.sh").read_text(encoding="utf-8")
    block = script.split('case "$TERMS_RC" in', 1)[1].split("esac", 1)[0]
    listed = {c for line in block.splitlines() if ")" in line
              for c in line.split(")", 1)[0].strip().split("|")}
    assert str(code) in listed
