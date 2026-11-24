"""Tests for scripts/package/abi-gate.sh failing closed.

The gate proves the manylinux bundle stays under the glibc 2.28 floor. A run
that inspected no ELF at all (missing file/readelf, or an archive with no
binaries) proves nothing and must not print PASS.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

ABI_GATE = Path(__file__).parents[1] / "package" / "abi-gate.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("readelf") is None or shutil.which("file") is None,
    reason="needs binutils readelf and file(1)",
)


def _zip(tmp_path: Path, members: dict[str, Path | str]) -> Path:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for name, src in members.items():
            if isinstance(src, Path):
                zf.write(src, f"activitywatch/{name}")
            else:
                zf.writestr(f"activitywatch/{name}", src)
    return archive


def _stub(bindir: Path, name: str, body: str) -> None:
    bindir.mkdir(exist_ok=True)
    path = bindir / name
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_gate(tmp_path: Path, archive: Path, bindir: Path | None = None):
    env = dict(os.environ)
    if bindir is not None:
        env["PATH"] = f"{bindir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(ABI_GATE), str(archive)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_archive_without_elfs_fails(tmp_path: Path) -> None:
    archive = _zip(tmp_path, {"README.txt": "no binaries here\n"})
    result = run_gate(tmp_path, archive)
    assert result.returncode != 0
    assert "PASS" not in result.stdout


def test_broken_file_tool_fails(tmp_path: Path) -> None:
    archive = _zip(tmp_path, {"aw-qt": Path(shutil.which("ls") or "/bin/ls")})
    bindir = tmp_path / "bin"
    _stub(bindir, "file", "exit 127\n")
    result = run_gate(tmp_path, archive, bindir)
    assert result.returncode != 0
    assert "PASS" not in result.stdout


def test_broken_readelf_fails(tmp_path: Path) -> None:
    archive = _zip(tmp_path, {"aw-qt": Path(shutil.which("ls") or "/bin/ls")})
    bindir = tmp_path / "bin"
    _stub(bindir, "readelf", "exit 127\n")
    result = run_gate(tmp_path, archive, bindir)
    assert result.returncode != 0
    assert "PASS" not in result.stdout


def test_real_binary_is_scanned(tmp_path: Path) -> None:
    # Host binaries may legitimately exceed the floor; either verdict is fine
    # as long as the binary was actually inspected.
    archive = _zip(tmp_path, {"aw-qt": Path(shutil.which("ls") or "/bin/ls")})
    result = run_gate(tmp_path, archive)
    assert "ELFs with GLIBC refs: 1 / 1" in result.stdout, result.stdout
    assert result.returncode in (0, 1)
