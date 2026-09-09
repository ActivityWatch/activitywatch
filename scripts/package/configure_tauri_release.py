#!/usr/bin/env python3
"""Set the compiled updater version and isolate Research Edition update trust."""

import argparse
import base64
import binascii
import json
import os
import sys
from pathlib import Path

from generate_latest_json import tauri_version

RESEARCH_ENDPOINT = (
    "https://raw.githubusercontent.com/ActivityWatch/activitywatch/"
    "research-updates/latest-research.json"
)
STANDARD_ENDPOINT = "https://github.com/ActivityWatch/activitywatch/releases/latest/download/latest.json"


def msi_rejects(version: str) -> bool:
    """True if Tauri's msi (WiX) bundler will reject this SemVer version.

    The msi target requires the optional pre-release identifier to be
    numeric-only (e.g. "0.14.0-5"), unlike nsis or the other bundle formats.
    AW's own pre-release scheme ("0.14.0-beta.5", "0.14.0-dev.gabc1234")
    fails that check every time.
    """
    if "-" not in version:
        return False
    prerelease = version.split("-", 1)[1]
    return not all(part.isdigit() for part in prerelease.split("."))


def public_key(encoded: str) -> bytes:
    """Read Tauri's base64-wrapped minisign public key, ignoring its comment."""
    try:
        lines = base64.b64decode(encoded, validate=True).decode("ascii").splitlines()
        if len(lines) != 2 or not lines[0].startswith("untrusted comment: "):
            raise ValueError("invalid public key envelope")
        packet = base64.b64decode(lines[1], validate=True)
        if len(packet) != 42 or packet[:2] != b"Ed":
            raise ValueError("invalid public key packet")
        return packet[10:]
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Expected a base64-encoded minisign public key") from exc


def configure(
    path: Path,
    version: str,
    research: bool,
    require_signing_key: bool,
    *,
    platform: str = sys.platform,
) -> None:
    config = json.loads(path.read_text(encoding="utf-8"))
    tv = tauri_version(version)
    config["version"] = tv
    if platform == "win32" and msi_rejects(tv):
        bundle = config.setdefault("bundle", {})
        if bundle.get("targets") == "all":
            # Windows only ever produces msi+nsis from "all"; drop msi and
            # keep nsis, which accepts the full AW pre-release scheme.
            bundle["targets"] = ["nsis"]
    if research:
        updater = config["plugins"]["updater"]
        if updater["endpoints"] != [STANDARD_ENDPOINT]:
            raise ValueError(
                "Unexpected source updater endpoint; review before patching"
            )
        research_key = os.environ.get("TAURI_UPDATER_PUBLIC_KEY_RESEARCH", "").strip()
        signing_key = os.environ.get("TAURI_SIGNING_PRIVATE_KEY", "").strip()
        if require_signing_key and (not research_key or not signing_key):
            raise ValueError(
                "Research releases require their own public and signing keys"
            )
        if research_key:
            if public_key(research_key) == public_key(updater["pubkey"]):
                raise ValueError(
                    "Research updater key must differ from the standard key"
                )
            updater["pubkey"] = research_key
            updater["endpoints"] = [RESEARCH_ENDPOINT]
        else:
            if signing_key:
                raise ValueError("Research signing key supplied without its public key")
            # Secretless PR smoke builds must never retain standard update trust.
            updater["pubkey"] = ""
            updater["endpoints"] = []
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--require-signing-key", action="store_true")
    args = parser.parse_args()
    try:
        configure(args.config, args.version, args.research, args.require_signing_key)
    except (ValueError, KeyError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
