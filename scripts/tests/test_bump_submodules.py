"""Tests for the confirm() prompt in scripts/bump-submodules.sh.

Without --yes, every commit/push step is gated on confirm(). An empty answer
means "yes" (Enter accepts), so end of input must not be read as an empty
answer: with stdin closed or not a terminal, the run would otherwise commit
and push to master with nobody confirming.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "bump-submodules.sh"


def _confirm_source() -> str:
    text = SCRIPT.read_text()
    match = re.search(r"^confirm\(\) \{\n.*?^\}\n", text, re.M | re.S)
    assert match, "confirm() not found in bump-submodules.sh"
    return match.group(0)


def run_confirm(stdin: str | None) -> subprocess.CompletedProcess[str]:
    script = (
        "set -euo pipefail\n"
        + _confirm_source()
        + "DRY=0 YES=0\n"
        + 'if confirm "push?"; then echo ACCEPTED; else echo SKIPPED; fi\n'
    )
    return subprocess.run(
        ["bash", "-c", script],
        input=stdin,
        stdin=subprocess.DEVNULL if stdin is None else None,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("\n", "ACCEPTED"), ("y\n", "ACCEPTED"), ("n\n", "SKIPPED")],
)
def test_interactive_answers(answer: str, expected: str) -> None:
    result = run_confirm(answer)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith(expected)


def test_quit_aborts() -> None:
    result = run_confirm("q\n")
    assert result.returncode != 0
    assert "ACCEPTED" not in result.stdout


@pytest.mark.parametrize("stdin", [None, ""], ids=["devnull", "closed-pipe"])
def test_end_of_input_is_not_yes(stdin: str | None) -> None:
    result = run_confirm(stdin)
    assert "ACCEPTED" not in result.stdout
    assert result.returncode != 0
