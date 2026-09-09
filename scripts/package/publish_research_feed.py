#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["semver>=3,<4"]
# ///
"""Validate and prepare a research feed commit; publish only with --publish."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen

from semver import Version

REPOSITORY = "ActivityWatch/activitywatch"
REF = "refs/heads/research-updates"
MANIFEST = "latest-research.json"
# Keep in step with build-tauri's release matrix. A reduced rollout needs review.
TARGETS = {
    "darwin-aarch64": ("app.tar.gz",),
    "darwin-x86_64": ("app.tar.gz",),
    "linux-aarch64": ("AppImage", "AppImage.tar.gz"),
    "linux-x86_64": ("AppImage", "AppImage.tar.gz"),
    "windows-x86_64": ("exe", "nsis.zip", "msi", "msi.zip"),
}


def public_bytes(url):
    """Unauthenticated reads prove the release/signature is publicly available."""
    request = Request(url, headers={"User-Agent": "ActivityWatch-research-publisher"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def validate_manifest(manifest, release, tag, fetch=None):
    if fetch is None:
        fetch = public_bytes
    if set(manifest) != {"version", "notes", "pub_date", "platforms"}:
        raise ValueError("Expected only the four static updater manifest fields")
    if not isinstance(manifest["notes"], str):
        raise ValueError("Manifest notes must be a string")
    date = manifest["pub_date"]
    if not isinstance(date, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
        date,
    ):
        raise ValueError("Manifest pub_date must be an RFC3339 timestamp")
    datetime.fromisoformat(date.replace("Z", "+00:00"))
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?-research", tag):
        raise ValueError("Expected a versioned research release tag")
    raw_version = tag[1 : -len("-research")]
    expected_version = re.sub(
        r"(a|b|rc)([0-9]+)$",
        lambda m: "-" + {"a": "alpha", "b": "beta", "rc": "rc"}[m[1]] + "." + m[2],
        raw_version,
    )
    Version.parse(expected_version)
    if manifest["version"] != expected_version:
        raise ValueError("Manifest version must match the normalized research tag")
    if (
        release["tag_name"] != tag
        or release["draft"] is not False
        or not release["published_at"]
        or release.get("immutable") is not True
    ):
        raise ValueError(
            "Release must be published, immutable, non-draft, and match the tag"
        )
    if set(manifest["platforms"]) != set(TARGETS):
        raise ValueError(
            "Manifest must contain exactly the complete required target matrix"
        )
    assets = {asset["name"]: asset for asset in release["assets"]}
    if len(assets) != len(release["assets"]):
        raise ValueError("Duplicate release asset names")
    base_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/"
    for target, entry in manifest["platforms"].items():
        if set(entry) != {"url", "signature"}:
            raise ValueError(f"Expected only url and signature for {target}")
        prefix = f"activitywatch-tauri-research-{raw_version}-{target}."
        names = [prefix + ext for ext in TARGETS[target]]
        matches = [name for name in names if entry["url"] == base_url + name]
        if len(matches) != 1:
            raise ValueError(
                f"Wrong edition, version, release, or bundle format for {target}"
            )
        name = matches[0]
        for asset_name in (name, name + ".sig"):
            asset = assets.get(asset_name)
            if (
                not asset
                or asset["state"] != "uploaded"
                or asset["size"] <= 0
                or asset["browser_download_url"] != base_url + asset_name
            ):
                raise ValueError(
                    f"Missing or invalid uploaded release asset: {asset_name}"
                )
        signature = entry["signature"]
        if (
            not isinstance(signature, str)
            or not signature.strip()
            or signature != fetch(base_url + name + ".sig").decode("utf-8").strip()
        ):
            raise ValueError(f"Missing or mismatched signature for {target}")


def git(repo, *args, input=None):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def remote_parent(repo, remote):
    result = git(repo, "ls-remote", "--refs", remote, REF)
    return result.split()[0] if result else "absent"


def prepare(repo, remote, expected_parent, manifest):
    """Create a new isolated checkout, retaining all existing feed branch files."""
    repo.mkdir(parents=True, exist_ok=False)
    git(repo, "init", "--quiet")
    if remote_parent(repo, remote) != expected_parent:
        raise ValueError("Stale expected parent; reread the feed and retry validation")
    if expected_parent != "absent":
        git(repo, "fetch", "--no-tags", remote, REF)
        if git(repo, "rev-parse", "FETCH_HEAD") != expected_parent:
            raise ValueError("Feed changed during fetch; reread and retry")
        git(repo, "checkout", "--detach", expected_parent)
        current = json.loads(git(repo, "show", f"{expected_parent}:{MANIFEST}"))
        old, new = Version.parse(current["version"]), Version.parse(manifest["version"])
        if new < old:
            raise ValueError("Refusing research feed version regression")
        if new == old:
            if manifest != current:
                raise ValueError("Conflicting content at equal SemVer precedence")
            return None
    else:
        git(repo, "checkout", "--orphan", "research-updates")
    # Replace any old symlink rather than following a path outside this checkout.
    path = repo / MANIFEST
    if path.is_symlink():
        path.unlink()
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    git(repo, "add", "--", MANIFEST)
    git(
        repo,
        "commit",
        "-m",
        f"chore(updater): offer research {manifest['version']}",
        "--",
        MANIFEST,
    )
    return git(repo, "rev-parse", "HEAD")


def publish(repo, remote, expected_parent, commit):
    """Assert the advertised parent in pre-push, then use Git's normal FF/CAS."""
    if git(repo, "rev-list", "--parents", "-n", "1", commit).split() != (
        [commit] if expected_parent == "absent" else [commit, expected_parent]
    ):
        raise ValueError("Candidate must be one commit on the expected parent")
    original_hook = Path(git(repo, "rev-parse", "--git-path", "hooks/pre-push"))
    if not original_hook.is_absolute():
        original_hook = repo / original_hook
    expected_oid = "0" * len(commit) if expected_parent == "absent" else expected_parent
    # Git sends the same advertised old OID to receive-pack, which checks it
    # atomically. Checking only ls-remote before push would leave a race window
    # for branch deletion/rewind. Preserve the site's existing pre-push policy.
    with tempfile.TemporaryDirectory(prefix="aw-feed-push-") as directory:
        hook = Path(directory) / "pre-push"
        hook.write_text(
            "#!/bin/sh\nexec "
            + shlex.quote(sys.executable)
            + " -c "
            + shlex.quote(
                "import os, subprocess, sys\n"
                "data = sys.stdin.read()\n"
                "rows = [line.split() for line in data.splitlines()]\n"
                f"expected = {expected_oid!r}\n"
                f"if len(rows) != 1 or rows[0][1:] != [{commit!r}, {REF!r}, expected]:\n"
                "    sys.exit('Feed parent changed during push; reread and retry')\n"
                f"hook = {str(original_hook)!r}\n"
                "if os.access(hook, os.X_OK):\n"
                "    sys.exit(subprocess.run([hook, *sys.argv[1:]], input=data, text=True).returncode)\n"
            )
            + ' "$@"\n',
            encoding="utf-8",
        )
        hook.chmod(0o755)
        git(
            repo,
            "-c",
            f"core.hooksPath={directory}",
            "-c",
            "push.followTags=false",
            "push",
            "--porcelain",
            remote,
            f"{commit}:{REF}",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--expected-parent",
        required=True,
        help="Full feed SHA, or 'absent' for provisioning",
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        type=Path,
        help="New directory to retain the reviewable commit",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Explicitly push after validation and preparation",
    )
    args = parser.parse_args(argv)
    remote = f"https://github.com/{REPOSITORY}.git"
    try:
        if args.expected_parent != "absent" and not re.fullmatch(
            r"[0-9a-f]{40}", args.expected_parent
        ):
            raise ValueError("Expected a full parent SHA or 'absent'")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        release = json.loads(
            public_bytes(
                f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{quote(args.tag, safe='')}"
            )
        )
        validate_manifest(manifest, release, args.tag)
        repo = args.work_dir.resolve()
        commit = prepare(repo, remote, args.expected_parent, manifest)
        if commit is None:
            print("NO-OP: identical manifest already published")
        elif args.publish:
            publish(repo, remote, args.expected_parent, commit)
            print(f"Published {commit} on {REF}")
        else:
            print(f"Prepared {commit} in {repo}; remote unchanged (no --publish)")
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        detail = (
            exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        )
        parser.exit(1, f"ERROR: {detail}\n")


if __name__ == "__main__":
    main()
