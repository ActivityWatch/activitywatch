"""Stamp the bundled Python executables before Windows zip/setup creation.

Use PyInstaller's resource writer so its appended executable archive is retained.
Rust/Tauri binaries and third-party helper executables are deliberately excluded.
Run this before Authenticode signing (resource updates invalidate signatures).
"""

import argparse
import re
from pathlib import Path

PYTHON_MODULES = {
    "aw-qt",
    "aw-server",
    "aw-watcher-afk",
    "aw-watcher-window",
    "aw-watcher-input",
}


def numeric_version(version):
    match = re.match(r"\d+(?:\.\d+){0,3}", version.lstrip("v"))
    if not match:
        raise ValueError(f"Invalid Windows version: {version!r}")
    parts = [int(n) for n in match.group(0).split(".")]
    if any(n > 65535 for n in parts):
        raise ValueError(f"Windows version components must fit in 16 bits: {version!r}")
    return tuple(parts + [0] * (4 - len(parts)))


def python_executables(bundle):
    return sorted(p for p in bundle.rglob("*.exe") if p.stem in PYTHON_MODULES)


def windows_version_info(name, version):
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    nums = numeric_version(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "ActivityWatch Contributors"),
                            StringStruct("FileDescription", name),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", name),
                            StringStruct("OriginalFilename", f"{name}.exe"),
                            StringStruct("ProductName", "ActivityWatch"),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()
    version = args.version.lstrip("v")
    numeric_version(version)
    executables = python_executables(args.bundle)
    if not executables:
        parser.error(f"No Python executables found in {args.bundle}")

    from PyInstaller.utils.win32.versioninfo import (
        read_version_info_from_executable,
        write_version_info_to_executable,
    )

    for exe in executables:
        info = windows_version_info(exe.stem, version)
        write_version_info_to_executable(str(exe), info)
        # Fail packaging rather than silently shipping missing version resources.
        actual = read_version_info_from_executable(str(exe))
        if actual is None or actual.toRaw() != info.toRaw():
            raise RuntimeError(f"Version resource verification failed: {exe}")
        print(f"Stamped {exe}: ActivityWatch {version}")


if __name__ == "__main__":
    main()
