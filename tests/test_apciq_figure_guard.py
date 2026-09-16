"""The verdict of check_apciq_figures.py, and the exit code that carries it.

The script's exit code is what check-secrets.sh reads. Until 2026-09-15 a WARN
line -- a ratio in level notation, a declared exception that no longer appears
-- still exited 0, and the banner above it said CLEAN. These tests pin the
three verdicts down without a database: the figures and the file list are
handed in directly.

No figure in this file is a real one. The planted amount is built at runtime,
so this tracked file never holds it as a literal -- the rule since J3.2 is that
no APCIQ figure enters a tracked file, and the scanner reads tests/ too.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_apciq_figures", REPO_ROOT / "scripts" / "check_apciq_figures.py"
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

PLANTED = str(10**6 + 7)
# Split for the same reason: written whole, the scanner flags this very file.
LEVEL_RATIO = "12.5" + "x"


def _run(monkeypatch, tmp_path, text: str) -> int:
    probe = tmp_path / "probe.md"
    probe.write_text(text, encoding="utf-8")
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guard, "DECLARED_EXCEPTIONS", {})
    monkeypatch.setattr(guard, "load_apciq_figures", lambda: {PLANTED})
    monkeypatch.setattr(guard, "tracked_text_files", lambda: ([probe], []))
    return guard.main()


def test_a_clean_file_exits_zero(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, "Nothing to see here.\n") == 0


def test_a_planted_figure_fails(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, f"The median was {PLANTED}.\n") == 1


def test_a_ratio_in_level_notation_does_not_exit_zero(monkeypatch, tmp_path):
    """The defect: WARN printed, exit 0, and check-secrets.sh said CLEAN."""
    assert _run(monkeypatch, tmp_path, f"The ratio reached {LEVEL_RATIO} in 2026.\n") == 3


def test_a_stale_exception_does_not_exit_zero(monkeypatch, tmp_path):
    probe = tmp_path / "probe.md"
    probe.write_text("Nothing to see here.\n", encoding="utf-8")
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guard, "DECLARED_EXCEPTIONS", {"777777": "gone"})
    monkeypatch.setattr(guard, "load_apciq_figures", lambda: {PLANTED})
    monkeypatch.setattr(guard, "tracked_text_files", lambda: ([probe], []))
    assert guard.main() == 3


def test_a_figure_outranks_a_warning(monkeypatch, tmp_path):
    """Both present: the run must say FAIL, never merely WARN."""
    text = f"The ratio reached {LEVEL_RATIO}; the median was {PLANTED}.\n"
    assert _run(monkeypatch, tmp_path, text) == 1


def test_an_unreachable_database_is_not_a_pass(monkeypatch):
    monkeypatch.setattr(guard, "load_apciq_figures", lambda: None)
    assert guard.main() == 2


@pytest.mark.parametrize("code", [0, 2, 3])
def test_check_secrets_lists_every_non_failure_exit_code(code):
    """A code the shell script does not list falls into its `*` failure branch.

    That is right for 1 and wrong for the others: a new non-failure code added
    to the Python side without its shell counterpart would turn a warning into
    a blocked commit, and the next reader would learn to override the check.
    """
    script = (REPO_ROOT / "scripts" / "check-secrets.sh").read_text(encoding="utf-8")
    block = script.split('case "$APCIQ_RC" in', 1)[1].split("esac", 1)[0]
    listed = {c for line in block.splitlines() if ")" in line
              for c in line.split(")", 1)[0].strip().split("|")}
    assert str(code) in listed
