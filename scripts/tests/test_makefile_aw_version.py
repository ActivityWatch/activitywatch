"""The bundle Makefile exports AW_VERSION on Windows for the Rust builds.

aw-server-rust and aw-notify embed it as the PE ProductVersion, so it must
match the version package-all.sh stamps on the Python executables: no "v"
prefix and no "-research" suffix.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
PROBE = 'aw-version-probe: ; @echo "[$$AW_VERSION]"'

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="needs GNU make")


def _probe(os_name: str | None, **env: str) -> str:
    full_env = {k: v for k, v in os.environ.items() if k != "AW_VERSION"}
    for key in (
        "GITHUB_REF",
        "GITHUB_REF_NAME",
        "TRAVIS_TAG",
        "APPVEYOR_REPO_TAG_NAME",
    ):
        full_env.pop(key, None)
    full_env.update(env)
    args = ["make", "-s", "--no-print-directory", "--eval", PROBE, "aw-version-probe"]
    if os_name:
        args.insert(1, f"OS={os_name}")
    out = subprocess.run(
        args, cwd=ROOT, env=full_env, capture_output=True, text=True, check=True
    )
    return out.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("os_name", ["MINGW64_NT-10.0-20348", "MSYS_NT-10.0-20348"])
def test_windows_exports_release_version_without_research_suffix(os_name: str) -> None:
    ref = "v0.14.0b5-research"
    assert (
        _probe(os_name, GITHUB_REF=f"refs/tags/{ref}", GITHUB_REF_NAME=ref)
        == "[0.14.0b5]"
    )


def test_windows_matches_getversion_without_v() -> None:
    expected = subprocess.run(
        [str(ROOT / "scripts/package/getversion.sh"), "--strip-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("GITHUB_REF", "TRAVIS", "APPVEYOR"))
        },
    ).stdout.strip()
    assert _probe("MINGW64_NT-10.0") == f"[{expected.removesuffix('-research')}]"


def test_explicit_aw_version_is_kept() -> None:
    assert _probe("MINGW64_NT-10.0", AW_VERSION="1.2.3") == "[1.2.3]"


@pytest.mark.parametrize("os_name", ["Linux", "Darwin"])
def test_not_exported_off_windows(os_name: str) -> None:
    assert _probe(os_name) == "[]"
