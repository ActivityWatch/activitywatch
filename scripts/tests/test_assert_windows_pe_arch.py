"""Tests for scripts/package/assert-windows-pe-arch.py.

A windows-x86_64 zip whose PE machine is 0xaa64 (ARM64) must fail. That is
the ActivityWatch/activitywatch#1519 shipping defect.
"""

from __future__ import annotations

import struct
import subprocess
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "package" / "assert-windows-pe-arch.py"

# IMAGE_FILE_MACHINE_*
MACHINE_AMD64 = 0x8664
MACHINE_ARM64 = 0xAA64
MACHINE_I386 = 0x14C


def make_pe(machine: int) -> bytes:
    """Minimal PE32+ stub with a chosen COFF Machine field."""
    dos = bytearray(64)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 64)
    pe = bytearray()
    pe += b"PE\x00\x00"
    pe += struct.pack("<HHIIIHH", machine, 0, 0, 0, 0, 0, 0)
    return bytes(dos) + bytes(pe)


def make_zip(tmp_path: Path, name: str, payload: bytes) -> Path:
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr(name, payload)
    return zpath


def run_assert(zip_path: Path, expected: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), str(zip_path), expected],
        capture_output=True,
        text=True,
        check=False,
    )


def test_x86_64_zip_with_amd64_pe_passes(tmp_path: Path):
    zpath = make_zip(tmp_path, "activitywatch/aw-qt.exe", make_pe(MACHINE_AMD64))
    result = run_assert(zpath, "x86_64")
    assert result.returncode == 0, result.stderr + result.stdout


def test_x86_64_zip_with_arm64_pe_fails(tmp_path: Path):
    zpath = make_zip(tmp_path, "activitywatch/aw-qt.exe", make_pe(MACHINE_ARM64))
    result = run_assert(zpath, "x86_64")
    assert result.returncode == 1
    assert "0xaa64" in result.stderr.lower() or "0xAA64" in result.stderr or "aa64" in result.stderr.lower()


def test_aarch64_zip_with_arm64_pe_passes(tmp_path: Path):
    zpath = make_zip(tmp_path, "activitywatch/aw-qt.exe", make_pe(MACHINE_ARM64))
    result = run_assert(zpath, "aarch64")
    assert result.returncode == 0, result.stderr + result.stdout


def test_mixed_pe_in_x86_64_zip_fails(tmp_path: Path):
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("activitywatch/aw-qt.exe", make_pe(MACHINE_AMD64))
        zf.writestr("activitywatch/aw-server.exe", make_pe(MACHINE_ARM64))
    result = run_assert(zpath, "x86_64")
    assert result.returncode == 1


def test_empty_zip_fails(tmp_path: Path):
    zpath = tmp_path / "empty.zip"
    zipfile.ZipFile(zpath, "w").close()
    result = run_assert(zpath, "x86_64")
    assert result.returncode != 0


def test_package_all_invokes_pe_assert():
    package = (Path(__file__).parents[1] / "package" / "package-all.sh").read_text()
    assert "assert-windows-pe-arch.py" in package
