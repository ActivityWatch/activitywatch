#!/usr/bin/env python3
"""Patch aw-qt's default config for Research Edition builds.

Flips `autostart_on_first_run` from false to true in aw_qt/config.py's
default_config, so participant machines register start-at-login on first
launch (aw-qt#131) without any setup steps. The user can still disable it
from the tray afterwards; aw-qt never re-enables once its marker is written.

Run as part of the CI build for research edition:
    python3 scripts/patch_research_edition_awqt.py <path/to/aw_qt/config.py>

Fails closed if the key is absent, which means the aw-qt submodule pin
predates aw-qt#131 — bump the pin rather than shipping a research build
that silently loses reboot-survival.
"""
import pathlib
import sys

OLD = "autostart_on_first_run = false"
NEW = "autostart_on_first_run = true"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path/to/aw_qt/config.py>", file=sys.stderr)
        return 2

    path = pathlib.Path(sys.argv[1])
    try:
        text = path.read_text()
    except FileNotFoundError:
        print(f"ERROR: {path} not found - is the aw-qt submodule checked out?", file=sys.stderr)
        return 1

    # Only patch the first occurrence: the [aw-qt] section default. The
    # [aw-qt-testing] section keeps autostart off.
    if OLD not in text:
        print(
            f"ERROR: {OLD!r} not found in {path} - aw-qt submodule pin "
            "predates aw-qt#131, refusing to build research edition without "
            "first-run autostart",
            file=sys.stderr,
        )
        return 1

    path.write_text(text.replace(OLD, NEW, 1))
    print(f"Patched {path}: {OLD} -> {NEW} (first occurrence)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
