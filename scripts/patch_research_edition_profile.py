#!/usr/bin/env python3
"""Bake the Research Edition profile identity into the bundle at release time.

The research profile is *build identity*, not a launch argument. A login item
that passes ``--profile research`` misses double-click, Spotlight, and the
updater relaunch, and every one of those would silently start ``default`` and
pollute a participant's standard install. So the research build patches the
no-information fallbacks in the sources it ships, before they are compiled or
collected:

1. **Profile**: every "no ``--profile``, no ``AW_PROFILE``" fallback resolves to
   ``research`` instead of ``default``. Both launchers (aw-qt, aw-tauri), both
   servers, and aw-client (the watchers' library) are patched, so any binary in
   the bundle defaults to the research instance no matter how it was started.
   The launchers then *set* ``AW_PROFILE=research`` for their children, and
   aw-core/aw-tauri dirs put everything under ``activitywatch-research/``.

   ``DEFAULT_PROFILE`` itself is deliberately **not** flipped: it means "the
   ordinary install" in suffix/dir/lockfile/``export_profile`` logic, and
   flipping it would make the research build share dirs and lockfile with a
   standard install — the exact collision this patch exists to prevent.

2. **Port**: the built-in 5600 default becomes 5667 in both servers, in
   aw-client, and in aw-qt's tray/manager fallbacks, so a fresh research
   profile binds 5667 without any config file existing yet.

3. **macOS bundle identity**: ``CFBundleIdentifier`` becomes
   ``net.activitywatch.ActivityWatch-research`` (Tauri: ``net.activitywatch.tauri-research``)
   with ``CFBundleName`` "ActivityWatch Research", so dual-run next to a
   standard install is a distinct LaunchServices identity with its own login
   item and TCC grant, not a shared slot.

Usage (from the repository root, after ``make test``, before ``make package``):

    python3 scripts/patch_research_edition_profile.py qt      # build-qt jobs
    python3 scripts/patch_research_edition_profile.py tauri   # build-tauri job
    python3 scripts/patch_research_edition_profile.py qt --check   # verify only

Every patch is fail-closed: if a target string is missing or ambiguous, the
script exits non-zero and the research build must not ship — a silent miss
here means a bundle that says "Research Edition" but runs ``profile=default``
on port 5600. Bump the submodule pin or update the table; never skip.

Run this **after** the module test suites: they assert the ordinary defaults
(``resolve_profile(None) == "default"``, port 5600) and would fail on the
patched tree. Python modules are editable installs, so PyInstaller collects
the patched source at package time; Rust binaries need a rebuild afterwards.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence

RESEARCH_PROFILE = "research"
RESEARCH_PORT = 5667
BUNDLE_ID = "net.activitywatch.ActivityWatch-research"
TAURI_IDENTIFIER = "net.activitywatch.tauri-research"
BUNDLE_NAME = "ActivityWatch Research"


@dataclass(frozen=True)
class Patch:
    """One exact, unique substring replacement in one file."""

    path: str
    old: str
    new: str
    why: str


# --- profile fallbacks ------------------------------------------------------

_PY_FALLBACK = "        return TESTING_PROFILE if testing else DEFAULT_PROFILE\n"
_PY_FALLBACK_NEW = "        return TESTING_PROFILE if testing else BUILD_PROFILE\n"


def _python_profile_patches(path: str) -> List[Patch]:
    """aw-qt / aw-server / aw-client share one profile module layout.

    Three no-information fallbacks return ``DEFAULT_PROFILE``: the ``None``
    branch of ``resolve_profile`` and the unset/invalid branches of
    ``profile_from_env``. All three become ``BUILD_PROFILE``.
    """
    return [
        Patch(
            path,
            'DEFAULT_PROFILE = "default"\nTESTING_PROFILE = "testing"\n',
            'DEFAULT_PROFILE = "default"\nTESTING_PROFILE = "testing"\n'
            "#: Research Edition build identity (baked at release time). Used only\n"
            "#: as the no-flag/no-env fallback; DEFAULT_PROFILE still means the\n"
            "#: ordinary install for suffix/dir/lockfile/export logic.\n"
            f'BUILD_PROFILE = "{RESEARCH_PROFILE}"\n',
            "declare BUILD_PROFILE next to DEFAULT_PROFILE",
        ),
        Patch(
            path,
            "    if profile is None:\n" + _PY_FALLBACK,
            "    if profile is None:\n" + _PY_FALLBACK_NEW,
            "resolve_profile(None) falls back to the build profile",
        ),
        Patch(
            path,
            "    if not profile:\n" + _PY_FALLBACK,
            "    if not profile:\n" + _PY_FALLBACK_NEW,
            "profile_from_env with AW_PROFILE unset falls back to the build profile",
        ),
        Patch(
            path,
            "    except ValueError:\n" + _PY_FALLBACK,
            "    except ValueError:\n" + _PY_FALLBACK_NEW,
            "profile_from_env with an invalid AW_PROFILE falls back to the build profile",
        ),
    ]


PROFILE_PATCHES_QT: List[Patch] = [
    *_python_profile_patches("aw-qt/aw_qt/profile.py"),
    *_python_profile_patches("aw-server/aw_server/profile.py"),
    *_python_profile_patches("aw-client/aw_client/profile.py"),
    Patch(
        "aw-server-rust/aw-server/src/main.rs",
        '                } else {\n                    "default".to_string()\n                }\n',
        f'                }} else {{\n                    "{RESEARCH_PROFILE}".to_string()\n                }}\n',
        "aw-server-rust with no --profile and no AW_PROFILE runs the build profile",
    ),
]

PROFILE_PATCHES_TAURI: List[Patch] = [
    # Watchers in the Tauri bundle are the same Python modules.
    *_python_profile_patches("aw-client/aw_client/profile.py"),
    Patch(
        "aw-tauri/src-tauri/src/profile.rs",
        'pub const DEFAULT_PROFILE: &str = "default";\n',
        'pub const DEFAULT_PROFILE: &str = "default";\n'
        "/// Research Edition build identity (baked at release time). Only the\n"
        "/// no-flag/no-env fallback; DEFAULT_PROFILE still means the ordinary install.\n"
        f'pub const BUILD_PROFILE: &str = "{RESEARCH_PROFILE}";\n',
        "declare BUILD_PROFILE next to DEFAULT_PROFILE",
    ),
    Patch(
        "aw-tauri/src-tauri/src/profile.rs",
        "        None => Ok(DEFAULT_PROFILE.to_string()),\n",
        "        None => Ok(BUILD_PROFILE.to_string()),\n",
        "resolve_profile with no --profile and no AW_PROFILE runs the build profile",
    ),
    Patch(
        "aw-tauri/src-tauri/src/profile.rs",
        "        _ => DEFAULT_PROFILE.to_string(),\n",
        "        _ => BUILD_PROFILE.to_string(),\n",
        "current_profile() before export falls back to the build profile",
    ),
]

# --- port -------------------------------------------------------------------

PORT_PATCHES_QT: List[Patch] = [
    Patch(
        "aw-server/aw_server/config.py",
        'port = "5600"\n',
        f'port = "{RESEARCH_PORT}"\n',
        "aw-server default_config [server] port",
    ),
    Patch(
        "aw-server/aw_server/config.py",
        "    return 5666 if is_testing(profile) else 5600\n",
        f"    return 5666 if is_testing(profile) else {RESEARCH_PORT}\n",
        "aw-server default_port()",
    ),
    Patch(
        "aw-server-rust/aw-server/src/config.rs",
        "    } else {\n        5600\n    }\n",
        f"    }} else {{\n        {RESEARCH_PORT}\n    }}\n",
        "aw-server-rust default_port()",
    ),
    Patch(
        "aw-client/aw_client/config.py",
        'port = "5600"\n',
        f'port = "{RESEARCH_PORT}"\n',
        "aw-client default_config [server] port",
    ),
    Patch(
        "aw-client/aw_client/config.py",
        '                _user_config_dir(f"{_DEFAULT_APPNAME}-{profile}"),\n'
        '                "aw-server-rust",\n'
        '                "config.toml",\n'
        "            ),\n"
        "            5600,\n",
        '                _user_config_dir(f"{_DEFAULT_APPNAME}-{profile}"),\n'
        '                "aw-server-rust",\n'
        '                "config.toml",\n'
        "            ),\n"
        f"            {RESEARCH_PORT},\n",
        "aw-client api-key lookup default port for a named profile",
    ),
    Patch(
        "aw-qt/aw_qt/config.py",
        "    default_port = 5666 if is_testing(profile) else 5600\n",
        f"    default_port = 5666 if is_testing(profile) else {RESEARCH_PORT}\n",
        "aw-qt _read_server_port fallback",
    ),
    Patch(
        "aw-qt/aw_qt/manager.py",
        "        default_port = 5666 if testing else 5600\n",
        f"        default_port = 5666 if testing else {RESEARCH_PORT}\n",
        "aw-qt external-server probe fallback",
    ),
    Patch(
        "aw-qt/aw_qt/trayicon.py",
        "            port = 5666 if testing else 5600\n",
        f"            port = 5666 if testing else {RESEARCH_PORT}\n",
        "aw-qt tray root_url fallback",
    ),
]

PORT_PATCHES_TAURI: List[Patch] = [
    # aw-tauri embeds aw-server-rust in-process and passes its own config
    # port, so the server crate's default_port() is irrelevant here.
    Patch(
        "aw-tauri/src-tauri/src/lib.rs",
        "        UserConfig {\n            port: 5600,\n",
        f"        UserConfig {{\n            port: {RESEARCH_PORT},\n",
        "aw-tauri UserConfig::default port",
    ),
    Patch(
        "aw-client/aw_client/config.py",
        'port = "5600"\n',
        f'port = "{RESEARCH_PORT}"\n',
        "aw-client default_config [server] port",
    ),
    Patch(
        "aw-client/aw_client/config.py",
        '                _user_config_dir(f"{_DEFAULT_APPNAME}-{profile}"),\n'
        '                "aw-server-rust",\n'
        '                "config.toml",\n'
        "            ),\n"
        "            5600,\n",
        '                _user_config_dir(f"{_DEFAULT_APPNAME}-{profile}"),\n'
        '                "aw-server-rust",\n'
        '                "config.toml",\n'
        "            ),\n"
        f"            {RESEARCH_PORT},\n",
        "aw-client api-key lookup default port for a named profile",
    ),
]

# --- macOS bundle identity ----------------------------------------------------

BUNDLE_PATCHES_QT: List[Patch] = [
    Patch(
        "aw.spec",
        '        bundle_identifier="net.activitywatch.ActivityWatch",\n',
        f'        bundle_identifier="{BUNDLE_ID}",\n',
        "PyInstaller BUNDLE identifier",
    ),
    Patch(
        "aw.spec",
        '            "CFBundleExecutable": "MacOS/aw-qt",\n',
        f'            "CFBundleName": "{BUNDLE_NAME}",\n'
        '            "CFBundleExecutable": "MacOS/aw-qt",\n',
        "PyInstaller BUNDLE display name",
    ),
    Patch(
        "scripts/notarize.sh",
        "bundleid=net.activitywatch.ActivityWatch # Match aw.spec\n",
        f"bundleid={BUNDLE_ID} # Match aw.spec\n",
        "notarization bundle id",
    ),
]

BUNDLE_PATCHES_TAURI: List[Patch] = [
    Patch(
        "scripts/package/build_app_tauri.sh",
        'BUNDLE_ID="net.activitywatch.ActivityWatch"\n',
        f'BUNDLE_ID="{BUNDLE_ID}"\n',
        "Tauri .app CFBundleIdentifier",
    ),
    Patch(
        "scripts/package/build_app_tauri.sh",
        "    <key>CFBundleName</key>\n    <string>${APP_NAME}</string>\n",
        f"    <key>CFBundleName</key>\n    <string>{BUNDLE_NAME}</string>\n",
        "Tauri .app CFBundleName",
    ),
    Patch(
        "aw-tauri/src-tauri/tauri.conf.json",
        '  "identifier": "net.activitywatch.tauri",\n',
        f'  "identifier": "{TAURI_IDENTIFIER}",\n',
        "Tauri identifier (single-instance slot on macOS/Windows, installer identity)",
    ),
    Patch(
        "scripts/notarize.sh",
        "bundleid=net.activitywatch.ActivityWatch # Match aw.spec\n",
        f"bundleid={BUNDLE_ID} # Match aw.spec\n",
        "notarization bundle id",
    ),
]

TARGETS = {
    "qt": PROFILE_PATCHES_QT + PORT_PATCHES_QT + BUNDLE_PATCHES_QT,
    "tauri": PROFILE_PATCHES_TAURI + PORT_PATCHES_TAURI + BUNDLE_PATCHES_TAURI,
}


class PatchError(Exception):
    pass


def _group_by_path(patches: Iterable[Patch]) -> "dict[str, List[Patch]]":
    grouped: "dict[str, List[Patch]]" = {}
    for patch in patches:
        grouped.setdefault(patch.path, []).append(patch)
    return grouped


def apply_patches(
    root: pathlib.Path, patches: Sequence[Patch], check: bool = False
) -> List[str]:
    """Apply (or with ``check`` only verify) every patch under ``root``.

    All targets in a file are validated before any of them is written, and a
    file is only written once all its patches apply. Any missing or ambiguous
    target raises :class:`PatchError` naming the file and the patch's purpose,
    so a stale submodule pin fails the release instead of shipping a bundle
    that runs the default profile.
    """
    applied: List[str] = []
    for rel_path, file_patches in _group_by_path(patches).items():
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise PatchError(
                f"{rel_path}: not found - is the submodule checked out?"
            ) from None

        for patch in file_patches:
            if patch.new in text:
                # Declaration inserts keep `old` as a prefix of `new`, so a
                # second run would silently double-insert without this check.
                raise PatchError(
                    f"{rel_path}: [{patch.why}] is already applied - refusing to "
                    "patch a tree twice"
                )
            occurrences = text.count(patch.old)
            if occurrences != 1:
                raise PatchError(
                    f"{rel_path}: expected exactly one match for [{patch.why}], "
                    f"found {occurrences}. The source drifted from what this "
                    "patcher targets - refusing to ship a research build with "
                    "the default profile/port/bundle id."
                )
            text = text.replace(patch.old, patch.new, 1)
            applied.append(f"{rel_path}: {patch.why}")

        if not check:
            path.write_text(text, encoding="utf-8")
    return applied


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", choices=sorted(TARGETS), help="which bundle is being built"
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify every target string is present and unique; write nothing",
    )
    args = parser.parse_args(argv)

    try:
        applied = apply_patches(args.root, TARGETS[args.target], check=args.check)
    except PatchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    verb = "Verified" if args.check else "Patched"
    for line in applied:
        print(f"{verb} {line}")
    print(
        f"{verb} {len(applied)} research edition site(s) for {args.target}: "
        f"profile={RESEARCH_PROFILE} port={RESEARCH_PORT} bundle={BUNDLE_ID}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
