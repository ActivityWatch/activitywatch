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


@pytest.mark.parametrize(
    ("answer", "committed", "exit_code", "edit"),
    [
        ("", False, 1, ""),
        ("q\n", False, 1, ""),
        ("n\n", False, 0, ""),
        ("\n", True, 1, ""),
        ("\n\n", True, 0, ""),
        ("q\n", False, 1, "worktree"),
        ("q\n", False, 1, "index"),
        ("n\n", False, 0, "worktree"),
        ("", False, 1, "index"),
    ],
    ids=[
        "eof",
        "quit",
        "decline",
        "push-eof",
        "accept",
        "quit-edited",
        "quit-staged",
        "decline-edited",
        "eof-staged",
    ],
)
def test_relock_prompt_leaves_clean_tree(
    tmp_path: Path, answer: str, committed: bool, exit_code: int, edit: str
) -> None:
    """Exercise the real relock branch, including confirm's process-level exit."""
    tauri = tmp_path / "aw-tauri"
    lock = tauri / "src-tauri" / "Cargo.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("old lock\n")

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(tauri), *args], text=True
        ).strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("config", "core.hooksPath", "/dev/null")
    git("add", ".")
    git("commit", "-qm", "initial lock")
    before = git("rev-parse", "HEAD")
    text = SCRIPT.read_text()
    helpers = text.split(
        "# ---------------------------------------------------------------- helpers\n"
    )[1]
    helpers = helpers.split(
        "# ---------------------------------------------------------------- preflight"
    )[0]
    relock = text.split(
        "# ---------------------------------------------------------------- 3. Tauri Cargo pin"
    )[1]
    relock = relock.split("\nelse\n", 1)[1]
    relock = relock.split(
        "# ---------------------------------------------------------------- 4. bundle"
    )[0]
    relock = relock.rsplit("\nfi", 1)[0]
    edit_prompt = ""
    if edit:
        edit_prompt = (
            _confirm_source().replace("confirm()", "prompt_confirm()")
            + "confirm() { echo 'user edit' > \"$LOCK\"; "
            + ("git -C aw-tauri add src-tauri/Cargo.lock; " if edit == "index" else "")
            + 'prompt_confirm "$@"; }\n'
        )
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail\n"
            + helpers
            + "DRY=0 YES=0 PUSH=1 SERVER_SHA=new\n"
            + "LOCK=aw-tauri/src-tauri/Cargo.lock\n"
            + "cargo() { echo 'aw-server-rust.git?branch=master#new' > Cargo.lock; }\n"
            # Do not push; the relock branch must clear cleanup before this prompt.
            + 'push_master() { confirm "push?"; }\n'
            + edit_prompt
            + relock,
        ],
        cwd=tmp_path,
        input=answer,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == exit_code, result.stderr
    if edit:
        assert lock.read_text() == "user edit\n"
        assert "changed" in result.stderr
        assert git("show", ":src-tauri/Cargo.lock") == (
            "user edit" if edit == "index" else "old lock"
        )
        assert git("rev-parse", "HEAD") == before
        return
    assert git("status", "--porcelain") == ""
    assert (git("rev-parse", "HEAD") != before) is committed
    assert lock.read_text() == (
        "aw-server-rust.git?branch=master#new\n" if committed else "old lock\n"
    )
