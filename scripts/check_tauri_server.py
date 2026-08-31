#!/usr/bin/env python3
"""Verify that Qt and Tauri bundle the same aw-server-rust revision."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


FIELD_RE = re.compile(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.|-|$)")
REVISION_RE = re.compile(r"#([0-9a-f]{40})$")


def major_minor(version: str) -> str:
    match = VERSION_RE.match(version)
    if not match:
        raise ValueError(f"invalid version: {version!r}")
    return ".".join(match.groups())


def read_package_version(cargo_toml: Path) -> str:
    in_package = False
    for line in cargo_toml.read_text(encoding="utf-8").splitlines():
        if line.strip() == "[package]":
            in_package = True
            continue
        if in_package and line.startswith("["):
            break
        if in_package:
            match = re.match(r'^version\s*=\s*"([^"]+)"', line)
            if match:
                return match.group(1)
    raise ValueError(f"no [package].version in {cargo_toml}")


def read_locked_server(cargo_lock: Path) -> Tuple[str, str]:
    matches = []
    for block in re.split(
        r"(?m)^\[\[package\]\]\s*$", cargo_lock.read_text(encoding="utf-8")
    ):
        fields = dict(FIELD_RE.findall(block))
        source = fields.get("source", "")
        if (
            fields.get("name") == "aw-server"
            and "ActivityWatch/aw-server-rust" in source
        ):
            revision = REVISION_RE.search(source)
            if not revision:
                raise ValueError(
                    f"aw-server source has no full Git revision: {source!r}"
                )
            matches.append((fields["version"], revision.group(1)))

    if len(matches) != 1:
        raise ValueError(
            f"expected one Git-locked aw-server package in {cargo_lock}, found {len(matches)}"
        )
    return matches[0]


def validation_errors(
    release_version: Optional[str],
    submodule_version: str,
    submodule_revision: str,
    tauri_version: str,
    tauri_revision: str,
) -> List[str]:
    errors = []
    if release_version is not None:
        release_line = major_minor(release_version)
        if major_minor(submodule_version) != release_line:
            errors.append(
                f"aw-server-rust submodule version {submodule_version} does not match "
                f"release line {release_line}"
            )
        if major_minor(tauri_version) != release_line:
            errors.append(
                f"Tauri locks aw-server {tauri_version}, which does not match release line "
                f"{release_line}"
            )
    if tauri_revision != submodule_revision:
        errors.append(
            f"Tauri locks aw-server-rust {tauri_revision[:12]}, but the release "
            f"submodule is {submodule_revision[:12]}"
        )
    return errors


def sync_submodule(server_root: Path, revision: str) -> bool:
    """Check out the Tauri-locked revision in the top-level server submodule."""
    git_root = Path(
        subprocess.check_output(
            ["git", "-C", str(server_root), "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    ).resolve()
    if git_root != server_root.resolve():
        raise ValueError(
            f"aw-server-rust is not initialized as a Git submodule at {server_root}"
        )

    current_revision = subprocess.check_output(
        ["git", "-C", str(server_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if current_revision == revision:
        return False

    dirty = subprocess.check_output(
        [
            "git",
            "-C",
            str(server_root),
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--ignore-submodules=all",
        ],
        text=True,
    ).strip()
    if dirty:
        raise ValueError(
            f"refusing to replace dirty aw-server-rust checkout at {server_root}"
        )

    try:
        subprocess.run(
            ["git", "-C", str(server_root), "cat-file", "-e", f"{revision}^{{commit}}"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "-C", str(server_root), "fetch", "origin", revision], check=True
        )

    subprocess.run(
        ["git", "-C", str(server_root), "checkout", "--detach", revision], check=True
    )
    subprocess.run(
        ["git", "-C", str(server_root), "submodule", "update", "--init", "--recursive"],
        check=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "release_version",
        nargs="?",
        help="ActivityWatch version without the leading v (required unless --sync)",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="make the top-level aw-server-rust submodule follow Tauri's Cargo.lock",
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    if args.release_version is None and not args.sync:
        parser.error("release_version is required unless --sync is used")

    root = args.repo_root.resolve()
    server_root = root / "aw-server-rust"
    try:
        if args.sync:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "submodule",
                    "update",
                    "--init",
                    "aw-tauri",
                    "aw-server-rust",
                ],
                check=True,
            )
        tauri_version, tauri_revision = read_locked_server(
            root / "aw-tauri/src-tauri/Cargo.lock"
        )
        if args.sync:
            changed = sync_submodule(server_root, tauri_revision)
            if changed:
                print(f"Synced aw-server-rust to Tauri lock {tauri_revision[:12]}")
            else:
                print(f"aw-server-rust already matches Tauri lock {tauri_revision[:12]}")
        submodule_version = read_package_version(server_root / "aw-server/Cargo.toml")
        submodule_revision = subprocess.check_output(
            ["git", "-C", str(server_root), "rev-parse", "HEAD"], text=True
        ).strip()
        errors = validation_errors(
            args.release_version,
            submodule_version,
            submodule_revision,
            tauri_version,
            tauri_revision,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(
            f"ERROR: could not inspect bundled aw-server versions: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.release_version is not None:
        print(f"ActivityWatch release: {args.release_version}")
    print(f"aw-server-rust:       {submodule_version} @ {submodule_revision[:12]}")
    print(f"Tauri Cargo.lock:     {tauri_version} @ {tauri_revision[:12]}")
    if errors:
        print("\nERROR: inconsistent aw-server build inputs:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if (
            args.release_version is not None
            and major_minor(tauri_version) != major_minor(args.release_version)
        ):
            print(
                "\nUpdate aw-tauri's Cargo.lock to the intended server release line, "
                "then run `make sync-tauri-server`.",
                file=sys.stderr,
            )
        else:
            print(
                "\nRun `make sync-tauri-server` to make the top-level submodule "
                "follow aw-tauri's Cargo.lock.",
                file=sys.stderr,
            )
        return 1

    print("OK: Qt and Tauri will bundle the same aw-server-rust revision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
