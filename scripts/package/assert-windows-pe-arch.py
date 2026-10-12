#!/usr/bin/env python3
"""Fail if a Windows zip's PE files do not match the declared arch token.

Used by package-all.sh after building activitywatch-*-windows-<arch>.zip so a
misnamed ARM64 zip cannot ship as windows-x86_64 (ActivityWatch/activitywatch#1519).
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path
from typing import BinaryIO

# IMAGE_FILE_MACHINE_* from winnt.h
MACHINE_I386 = 0x14C
MACHINE_AMD64 = 0x8664
MACHINE_ARM64 = 0xAA64

EXPECTED_MACHINE = {
    "x86_64": MACHINE_AMD64,
    "amd64": MACHINE_AMD64,
    "aarch64": MACHINE_ARM64,
    "arm64": MACHINE_ARM64,
    "x86": MACHINE_I386,
}

MACHINE_NAME = {
    MACHINE_I386: "i386",
    MACHINE_AMD64: "amd64/x86_64",
    MACHINE_ARM64: "arm64/aarch64",
}


def pe_machine(fh: BinaryIO) -> int | None:
    """Read the COFF Machine field at the DOS header's declared PE offset."""
    dos = fh.read(64)
    if len(dos) < 64 or dos[:2] != b"MZ":
        return None
    (pe_off,) = struct.unpack_from("<I", dos, 0x3C)
    fh.seek(pe_off)
    header = fh.read(6)
    if len(header) < 6 or header[:4] != b"PE\x00\x00":
        return None
    (machine,) = struct.unpack_from("<H", header, 4)
    return machine


def check_zip(zip_path: Path, expected_arch: str) -> int:
    expected_key = expected_arch.lower()
    if expected_key not in EXPECTED_MACHINE:
        print(
            f"ERROR: unsupported expected arch {expected_arch!r} "
            f"(need one of {sorted(EXPECTED_MACHINE)})",
            file=sys.stderr,
        )
        return 2
    expected = EXPECTED_MACHINE[expected_key]
    if not zipfile.is_zipfile(zip_path):
        print(f"ERROR: not a zip file: {zip_path}", file=sys.stderr)
        return 2

    pe_count = 0
    mismatches: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.lower()
            if not (name.endswith(".exe") or name.endswith(".dll")):
                continue
            with zf.open(info) as fh:
                machine = pe_machine(fh)
            if machine is None:
                print(
                    f"WARNING: {info.filename} is named like a PE file but has no PE header",
                    file=sys.stderr,
                )
                continue
            pe_count += 1
            if machine != expected:
                mismatches.append(
                    f"{info.filename}: machine 0x{machine:04x} "
                    f"({MACHINE_NAME.get(machine, 'unknown')}), "
                    f"expected 0x{expected:04x} ({MACHINE_NAME[expected]})"
                )

    if pe_count == 0:
        print(
            f"ERROR: {zip_path} contains no PE .exe/.dll files to check",
            file=sys.stderr,
        )
        return 1
    if mismatches:
        print(
            f"ERROR: {zip_path} declared arch {expected_arch} but PE files do not match:",
            file=sys.stderr,
        )
        for line in mismatches:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"OK: {pe_count} PE file(s) in {zip_path.name} match {expected_arch}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("expected_arch")
    args = parser.parse_args(argv)
    return check_zip(args.zip_path, args.expected_arch)


if __name__ == "__main__":
    sys.exit(main())
