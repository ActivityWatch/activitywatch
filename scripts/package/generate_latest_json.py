#!/usr/bin/env python3
"""Assemble a Tauri updater `latest.json` manifest from per-platform .sig files.

Expects updater artifacts to be named
`activitywatch-tauri-<version>-<platform-key>.<ext>` with a matching
`<...>.sig` file alongside it (as produced by the "Package Tauri updater
artifacts" step in release.yml), where <platform-key> is a Tauri
updater platform identifier such as "darwin-aarch64" or "linux-x86_64".
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument(
        "--repo", required=True, help="e.g. ActivityWatch/activitywatch"
    )
    parser.add_argument("--tag", required=True, help="e.g. v0.13.3")
    parser.add_argument("--dist", required=True, help="directory to search for *.sig files")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # Non-greedy platform group: extensions can be multi-part (.app.tar.gz,
    # .AppImage.tar.gz, .nsis.zip), so stop at the first dot after the
    # platform key rather than the last.
    pattern = re.compile(
        rf"^activitywatch-tauri-{re.escape(args.version)}-(?P<platform>.+?)\.(?P<ext>.+)$"
    )

    platforms = {}
    for root, _, files in os.walk(args.dist):
        for name in files:
            if not name.endswith(".sig"):
                continue
            asset_name = name[: -len(".sig")]
            m = pattern.match(asset_name)
            if not m:
                continue
            with open(os.path.join(root, name)) as f:
                signature = f.read().strip()
            platforms[m.group("platform")] = {
                "signature": signature,
                "url": (
                    f"https://github.com/{args.repo}/releases/download/"
                    f"{args.tag}/{asset_name}"
                ),
            }

    if not platforms:
        raise SystemExit(
            "No updater artifacts found - refusing to write an empty latest.json"
        )

    manifest = {
        "version": args.version,
        "notes": args.notes,
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": platforms,
    }

    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {args.output} with platforms: {', '.join(sorted(platforms))}")


if __name__ == "__main__":
    main()
