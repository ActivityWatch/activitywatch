#!/usr/bin/env python3
"""Assemble a Tauri updater manifest from per-platform .sig files.

Expects updater artifacts named
`activitywatch-tauri[-research]-<version>-<platform-key>.<ext>` with a
matching `<...>.sig` file alongside it (as produced by the "Package Tauri
updater artifacts" step in release.yml), where <platform-key> is a Tauri
updater platform identifier such as "darwin-aarch64" or "linux-x86_64".

Standard and Research Edition releases are partitioned by filename:

- standard:  `latest.json`           + `activitywatch-tauri-<ver>-...`
- research:  `latest-research.json`  + `activitywatch-tauri-research-<ver>-...`

so the two lines cannot overwrite each other's GitHub release assets or
share an updater endpoint.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone

EDITIONS = ("standard", "research")


def normalize_version(version: str) -> str:
    """Strip a leading 'v' and a trailing '-research' edition suffix."""
    if version.startswith("v"):
        version = version[1:]
    if version.endswith("-research"):
        version = version[: -len("-research")]
    return version


def infer_edition(tag: str, edition=None) -> str:
    if edition:
        if edition not in EDITIONS:
            raise ValueError(f"unknown edition {edition!r}")
        return edition
    return "research" if tag.endswith("-research") else "standard"


def asset_prefix(edition: str) -> str:
    if edition == "research":
        return "activitywatch-tauri-research"
    return "activitywatch-tauri"


def manifest_filename(edition: str) -> str:
    return "latest-research.json" if edition == "research" else "latest.json"


# Tauri v2 recommends NSIS for Windows updater bundles. When both NSIS and
# MSI signatures exist for the same platform key, keep NSIS regardless of
# os.walk order. Unlisted extensions share rank 0 (first one wins).
WINDOWS_BUNDLE_RANK = {
    "nsis.zip": 2,
    "exe": 1,
    "msi.zip": 0,
    "msi": 0,
}


def bundle_rank(ext: str) -> int:
    return WINDOWS_BUNDLE_RANK.get(ext, 0)


def collect_platforms(dist: str, version: str, repo: str, tag: str, edition: str) -> dict:
    prefix = asset_prefix(edition)
    # Non-greedy platform group: extensions can be multi-part (.app.tar.gz,
    # .AppImage.tar.gz, .nsis.zip), so stop at the first dot after the
    # platform key rather than the last.
    pattern = re.compile(
        rf"^{re.escape(prefix)}-{re.escape(version)}-(?P<platform>.+?)\.(?P<ext>.+)$"
    )

    platforms = {}
    chosen_ext = {}
    for root, _, files in os.walk(dist):
        for name in files:
            if not name.endswith(".sig"):
                continue
            asset_name = name[: -len(".sig")]
            m = pattern.match(asset_name)
            if not m:
                continue
            platform = m.group("platform")
            ext = m.group("ext")
            prev_ext = chosen_ext.get(platform)
            if prev_ext is not None and bundle_rank(ext) <= bundle_rank(prev_ext):
                continue
            with open(os.path.join(root, name)) as f:
                signature = f.read().strip()
            chosen_ext[platform] = ext
            platforms[platform] = {
                "signature": signature,
                "url": (
                    f"https://github.com/{repo}/releases/download/"
                    f"{tag}/{asset_name}"
                ),
            }
    return platforms


def build_manifest(version: str, notes: str, platforms: dict, pub_date=None) -> dict:
    if pub_date is None:
        pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": platforms,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument(
        "--repo", required=True, help="e.g. ActivityWatch/activitywatch"
    )
    parser.add_argument("--tag", required=True, help="e.g. v0.13.3 or v0.13.3-research")
    parser.add_argument(
        "--edition",
        choices=EDITIONS,
        default=None,
        help="Release line. Inferred from --tag (*-research) if omitted.",
    )
    parser.add_argument("--dist", required=True, help="directory to search for *.sig files")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    version = normalize_version(args.version)
    edition = infer_edition(args.tag, args.edition)
    platforms = collect_platforms(args.dist, version, args.repo, args.tag, edition)

    if not platforms:
        raise SystemExit(
            f"No {edition} updater artifacts found - refusing to write an empty "
            f"{os.path.basename(args.output)}"
        )

    manifest = build_manifest(version, args.notes, platforms)

    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {args.output} ({edition}) with platforms: {', '.join(sorted(platforms))}")


if __name__ == "__main__":
    main()
