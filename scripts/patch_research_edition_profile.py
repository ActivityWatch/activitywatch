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
   with ``CFBundleName`` "ActivityWatch Research" *and* on-disk bundle
   ``ActivityWatch-Research.app``, so dual-run next to a standard install is a
   distinct LaunchServices identity that does not overwrite
   ``/Applications/ActivityWatch.app``.

4. **Install identity**: Windows gets its own Inno ``AppId``, install dir,
   shortcuts and uninstall entry; Linux gets its own deb package name,
   ``/opt/activitywatch-research`` tree and desktop-entry filename. Bundle ids
   split LaunchServices, not the on-disk product -- without this a research
   installer *replaces* a participant's standard install.

5. **First-run autostart**: aw-qt writes its own login item / Startup shortcut /
   autostart ``.desktop``, under names independent of the installer's. Those are
   rebranded too, or the two editions overwrite each other's autostart even with
   every other identity split.

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
# Hyphenated on-disk stem so Makefile / notarize / CI paths stay unquoted.
# Dock and Spotlight still show CFBundleName ("ActivityWatch Research").
BUNDLE_DIR_STEM = "ActivityWatch-Research"

# Windows install identity. Inno Setup keys off AppId, not the display name: a
# research setup sharing the standard AppId registers as the *same* product, so
# it upgrades over an existing install and its uninstaller removes both. Own
# GUIDs give the research build its own install dir, Start-Menu/desktop/startup
# shortcuts and "Apps & features" entry, which is what dual-run requires.
WINDOWS_APPID_QT = "32024B9B-352E-4E97-AA56-9EEF143E5B70"
WINDOWS_APPID_TAURI = "70E2D4AB-8DA2-4BE0-8391-AB5B48653773"
# MSI upgrade code. Tauri derives this from `identifier` when unset, so the
# research build already differs today via the patched identifier — but that
# makes installer identity a silent side effect of an unrelated string. Pinning
# it means a future identifier change cannot collapse research MSIs onto the
# standard upgrade family. WixConfig exposes no product-code field (Tauri
# generates one per build); the upgrade code is what defines the product family,
# so it is the one that matters here.
WINDOWS_WIX_UPGRADE_CODE_TAURI = "ABF0AB0C-5BA0-4C2C-BF3E-797B2E1913DA"

# Linux install identity. The Qt deb is a single product on master:
# `Package: activitywatch`, `/opt/activitywatch`, and one `aw-qt.desktop`
# filename in both /etc/xdg/autostart and /usr/share/applications. Installing a
# research deb next to a standard one therefore *replaces* it (dpkg treats a
# same-named package as an upgrade) and its autostart entry overwrites the
# standard one. Own package name, own /opt tree and own desktop-entry filename
# is what makes the two editions co-installable.
LINUX_PACKAGE = "activitywatch-research"
LINUX_OPT_DIR = f"/opt/{LINUX_PACKAGE}"
LINUX_DESKTOP_FILENAME = f"{LINUX_PACKAGE}.desktop"
# Desktop-entry `Icon=` id. Only the AppImage actually installs an icon under
# this name (`linuxdeploy --icon-filename`); the deb ships none today. Patch
# both together so they cannot drift apart.
LINUX_ICON_ID = LINUX_PACKAGE
# macOS LaunchAgent label written by aw-qt's own first-run autostart (distinct
# from the .app bundle id, which the installer/LaunchServices own).
LAUNCH_AGENT_LABEL = "net.activitywatch.aw-qt-research"


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
        "aw.spec",
        '        name="ActivityWatch.app",\n',
        f'        name="{BUNDLE_DIR_STEM}.app",\n',
        "PyInstaller BUNDLE on-disk filename",
    ),
    Patch(
        "Makefile",
        "APP_BUNDLE ?= ActivityWatch\n",
        f"APP_BUNDLE ?= {BUNDLE_DIR_STEM}\n",
        "Makefile .app/.dmg stem",
    ),
    Patch(
        "scripts/notarize.sh",
        "bundleid=net.activitywatch.ActivityWatch # Match aw.spec\n",
        f"bundleid={BUNDLE_ID} # Match aw.spec\n",
        "notarization bundle id",
    ),
    Patch(
        "scripts/notarize.sh",
        "app=dist/ActivityWatch.app\n"
        "dmg=dist/ActivityWatch.dmg\n",
        f"app=dist/{BUNDLE_DIR_STEM}.app\n"
        f"dmg=dist/{BUNDLE_DIR_STEM}.dmg\n",
        "notarization .app/.dmg paths",
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
        "scripts/package/build_app_tauri.sh",
        'APP_NAME="ActivityWatch"\n',
        f'APP_NAME="{BUNDLE_DIR_STEM}"\n',
        "Tauri .app on-disk filename",
    ),
    Patch(
        "Makefile",
        "APP_BUNDLE ?= ActivityWatch\n",
        f"APP_BUNDLE ?= {BUNDLE_DIR_STEM}\n",
        "Makefile .app/.dmg stem",
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
    Patch(
        "scripts/notarize.sh",
        "app=dist/ActivityWatch.app\n"
        "dmg=dist/ActivityWatch.dmg\n",
        f"app=dist/{BUNDLE_DIR_STEM}.app\n"
        f"dmg=dist/{BUNDLE_DIR_STEM}.dmg\n",
        "notarization .app/.dmg paths",
    ),
]

# --- Windows install identity -------------------------------------------------
# Both .iss files derive AppName, DefaultDirName (Qt), the Start-Menu / desktop /
# {userstartup} shortcut names and UninstallDisplayName from `#define MyAppName`,
# so patching that one token cascades to every user-visible identity. AppId and
# OutputBaseFilename do not cascade and are patched explicitly.
#
# Note both .iss files ship `OutputBaseFilename=activitywatch-setup` on master,
# so the Qt and Tauri setups already overwrite each other in dist/. The research
# names below are distinct from each other as well as from standard, which also
# stops research artifacts from colliding on the release page.

WINDOWS_PATCHES_QT: List[Patch] = [
    Patch(
        "scripts/package/activitywatch-setup.iss",
        '#define MyAppName "ActivityWatch"\n',
        f'#define MyAppName "{BUNDLE_NAME}"\n',
        "Inno Qt product name (cascades to dir, shortcuts, uninstall entry)",
    ),
    Patch(
        "scripts/package/activitywatch-setup.iss",
        "AppId={{F226B8F4-3244-46E6-901D-0CE8035423E4}\n",
        f"AppId={{{{{WINDOWS_APPID_QT}}}\n",
        "Inno Qt AppId (separate product, not an upgrade of standard)",
    ),
    Patch(
        "scripts/package/activitywatch-setup.iss",
        "OutputBaseFilename=activitywatch-setup\n",
        "OutputBaseFilename=activitywatch-research-setup\n",
        "Inno Qt setup .exe filename",
    ),
]

WINDOWS_PATCHES_TAURI: List[Patch] = [
    Patch(
        "aw-tauri/src-tauri/tauri.conf.json",
        '  "bundle": {\n    "active": true,\n',
        '  "bundle": {\n    "active": true,\n'
        '    "windows": {\n'
        '      "wix": {\n'
        f'        "upgradeCode": "{WINDOWS_WIX_UPGRADE_CODE_TAURI}"\n'
        '      }\n'
        '    },\n',
        "Tauri WiX upgrade code (research MSIs are their own product family)",
    ),
    Patch(
        "scripts/package/aw-tauri.iss",
        '#define MyAppName "ActivityWatch (Tauri)"\n',
        f'#define MyAppName "{BUNDLE_NAME} (Tauri)"\n',
        "Inno Tauri product name (cascades to shortcuts, uninstall entry)",
    ),
    Patch(
        "scripts/package/aw-tauri.iss",
        "AppId={{983D0855-08C8-46BD-AEFB-3924581C6703}\n",
        f"AppId={{{{{WINDOWS_APPID_TAURI}}}\n",
        "Inno Tauri AppId (separate product, not an upgrade of standard Tauri)",
    ),
    Patch(
        "scripts/package/aw-tauri.iss",
        "DefaultDirName={autopf}\\ActivityWatch-Tauri\n",
        f"DefaultDirName={{autopf}}\\{BUNDLE_DIR_STEM}-Tauri\n",
        "Inno Tauri install directory",
    ),
    Patch(
        "scripts/package/aw-tauri.iss",
        "OutputBaseFilename=activitywatch-setup\n",
        "OutputBaseFilename=activitywatch-research-tauri-setup\n",
        "Inno Tauri setup .exe filename",
    ),
]


# --- Linux package identity ---------------------------------------------------
# Qt only: the Tauri Linux bundles come from Tauri's own bundler, whose package
# and desktop-entry names derive from `productName`. That is coupled to the
# cargo binary name (`mainBinaryName`), so splitting it needs a Tauri build to
# verify and is tracked separately.

LINUX_PATCHES_QT: List[Patch] = [
    Patch(
        "scripts/package/deb/control",
        "Package: activitywatch\n",
        f"Package: {LINUX_PACKAGE}\n",
        "deb package name (co-installable with the standard package)",
    ),
    Patch(
        "scripts/package/deb/control",
        "Description: Open source time tracker\n",
        "Description: Open source time tracker (Research Edition)\n",
        "deb package description",
    ),
    Patch(
        "scripts/package/package-deb.sh",
        'PKGDIR="activitywatch_$VERSION_NUM"\n',
        f'PKGDIR="{LINUX_PACKAGE}_$VERSION_NUM"\n',
        "deb staging dir (dpkg-deb names the .deb after it)",
    ),
    Patch(
        "scripts/package/package-deb.sh",
        "sudo mv activitywatch_${VERSION_NUM}.deb",
        f"sudo mv {LINUX_PACKAGE}_${{VERSION_NUM}}.deb",
        "deb output filename produced by dpkg-deb --build",
    ),
    Patch(
        "scripts/package/package-deb.sh",
        "cp -r dist/activitywatch/ $PKGDIR/opt/\n",
        f"cp -r dist/activitywatch/ $PKGDIR{LINUX_OPT_DIR}\n",
        "install tree location (/opt/activitywatch-research)",
    ),
    Patch(
        "scripts/package/package-deb.sh",
        "sudo sed -i 's!Exec=aw-qt!Exec=/opt/activitywatch/aw-qt!' "
        "$PKGDIR/opt/activitywatch/aw-qt.desktop\n"
        "sudo cp $PKGDIR/opt/activitywatch/aw-qt.desktop $PKGDIR/etc/xdg/autostart/\n"
        "sudo cp $PKGDIR/opt/activitywatch/aw-qt.desktop $PKGDIR/usr/share/applications/\n",
        f"sudo sed -i 's!Exec=aw-qt!Exec={LINUX_OPT_DIR}/aw-qt!' "
        f"$PKGDIR{LINUX_OPT_DIR}/aw-qt.desktop\n"
        f"sudo cp $PKGDIR{LINUX_OPT_DIR}/aw-qt.desktop "
        f"$PKGDIR/etc/xdg/autostart/{LINUX_DESKTOP_FILENAME}\n"
        f"sudo cp $PKGDIR{LINUX_OPT_DIR}/aw-qt.desktop "
        f"$PKGDIR/usr/share/applications/{LINUX_DESKTOP_FILENAME}\n",
        "Exec path plus distinct autostart/menu desktop-entry filename",
    ),
    Patch(
        "aw-qt/resources/aw-qt.desktop",
        "Name=ActivityWatch\n",
        f"Name={BUNDLE_NAME}\n",
        "desktop entry display name",
    ),
    Patch(
        "aw-qt/resources/aw-qt.desktop",
        "Icon=activitywatch\n",
        f"Icon={LINUX_ICON_ID}\n",
        "desktop entry icon id (matches the AppImage --icon-filename)",
    ),
    Patch(
        "scripts/package/package-appimage.sh",
        "--desktop-file ./activitywatch/aw-qt.desktop "
        "--icon-file ./activitywatch/media/logo/logo.png "
        "--icon-filename activitywatch\n",
        f"--desktop-file ./activitywatch/{LINUX_DESKTOP_FILENAME} "
        "--icon-file ./activitywatch/media/logo/logo.png "
        f"--icon-filename {LINUX_ICON_ID}\n",
        "AppImage desktop-entry filename and icon id",
    ),
    Patch(
        "scripts/package/package-appimage.sh",
        "# create AppRun\n",
        "# Research edition: linuxdeploy installs the desktop entry under its own\n"
        "# basename, so give it a distinct one - appimaged would otherwise\n"
        "# overwrite a standard install's entry on desktop integration.\n"
        f"cp ./activitywatch/aw-qt.desktop ./activitywatch/{LINUX_DESKTOP_FILENAME}\n"
        "\n# create AppRun\n",
        "AppImage: stage the research desktop entry under its own filename",
    ),
]

# --- first-run autostart identity ---------------------------------------------
# aw-qt writes its own autostart entry (config `autostart_on_first_run`). Those
# names are independent of the installer's: without this the two editions
# overwrite each other's login item / Startup shortcut / autostart .desktop even
# though every other identity is already split.

AUTOSTART_PATCHES_QT: List[Patch] = [
    Patch(
        "aw-qt/aw_qt/autostart.py",
        'APP_NAME = "ActivityWatch"\n',
        f'APP_NAME = "{BUNDLE_NAME}"\n',
        "Windows Run value + Startup shortcut name",
    ),
    Patch(
        "aw-qt/aw_qt/autostart.py",
        "    return _linux_autostart_dir() / DESKTOP_FILENAME\n",
        f'    return _linux_autostart_dir() / "{LINUX_DESKTOP_FILENAME}"\n',
        "Linux autostart entry filename (DESKTOP_FILENAME still names the "
        "shipped resource we copy from)",
    ),
    Patch(
        "aw-qt/aw_qt/autostart.py",
        'LAUNCH_AGENT_LABEL = "net.activitywatch.aw-qt"\n',
        f'LAUNCH_AGENT_LABEL = "{LAUNCH_AGENT_LABEL}"\n',
        "macOS LaunchAgent label and plist filename",
    ),
    Patch(
        "aw-qt/aw_qt/autostart.py",
        "Name=ActivityWatch\n",
        f"Name={BUNDLE_NAME}\n",
        "fallback desktop-entry template display name",
    ),
]


# --- first-run autostart identity (Tauri) --------------------------------------
# tauri_plugin_autostart derives its OS entry name from productName by default.
# Standard and research Tauri builds share productName="aw-tauri", so their
# autostart entries (Windows registry Run key, Linux ~/.config/autostart/ file)
# overwrite each other. Give the research build a distinct name by switching to
# the Builder API and setting app_name when BUILD_PROFILE is not the default.
# macOS uses different OS mechanisms (AppleScript vs LaunchAgent) so it doesn't
# collide, but the macos_launcher selection is included for completeness.
#
# This patch applies after PROFILE_PATCHES_TAURI, so BUILD_PROFILE and
# DEFAULT_PROFILE are both defined in the compiled profile module by the time
# the research binary runs.

AUTOSTART_PATCHES_TAURI: List[Patch] = [
    Patch(
        "aw-tauri/src-tauri/src/lib.rs",
        "        .plugin(tauri_plugin_autostart::init(\n"
        "            // AppleScript login items silently drop extra arguments; LaunchAgent\n"
        "            // writes a plist with ProgramArguments so --profile survives relogin.\n"
        "            if profile::is_default(&cli_args.profile) {\n"
        "                MacosLauncher::AppleScript\n"
        "            } else {\n"
        "                MacosLauncher::LaunchAgent\n"
        "            },\n"
        "            if profile::is_default(&cli_args.profile) {\n"
        "                Some(vec![])\n"
        "            } else {\n"
        "                Some(vec![\"--profile\", cli_args.profile.as_str()])\n"
        "            },\n"
        "        ))\n",
        "        .plugin({\n"
        "            // AppleScript login items silently drop extra arguments; LaunchAgent\n"
        "            // writes a plist with ProgramArguments so --profile survives relogin.\n"
        "            // Non-default BUILD_PROFILE means a research-edition binary: give it a\n"
        "            // distinct autostart entry name so editions don't overwrite each other.\n"
        "            let is_default_profile = profile::is_default(&cli_args.profile);\n"
        "            let args: Vec<&str> = if is_default_profile {\n"
        "                vec![]\n"
        "            } else {\n"
        "                vec![\"--profile\", cli_args.profile.as_str()]\n"
        "            };\n"
        "            #[allow(unused_mut)]\n"
        "            let mut b = tauri_plugin_autostart::Builder::new().args(args);\n"
        "            if profile::BUILD_PROFILE != profile::DEFAULT_PROFILE {\n"
        "                b = b.app_name(format!(\"aw-tauri-{}\", profile::BUILD_PROFILE));\n"
        "            }\n"
        "            #[cfg(target_os = \"macos\")]\n"
        "            {\n"
        "                b = b.macos_launcher(if is_default_profile {\n"
        "                    MacosLauncher::AppleScript\n"
        "                } else {\n"
        "                    MacosLauncher::LaunchAgent\n"
        "                });\n"
        "            }\n"
        "            b.build()\n"
        "        })\n",
        "tauri autostart: Builder with distinct app_name for research edition",
    ),
]


TARGETS = {
    "qt": (
        PROFILE_PATCHES_QT
        + PORT_PATCHES_QT
        + BUNDLE_PATCHES_QT
        + WINDOWS_PATCHES_QT
        + LINUX_PATCHES_QT
        + AUTOSTART_PATCHES_QT
    ),
    "tauri": (
        PROFILE_PATCHES_TAURI
        + PORT_PATCHES_TAURI
        + BUNDLE_PATCHES_TAURI
        + WINDOWS_PATCHES_TAURI
        + AUTOSTART_PATCHES_TAURI
    ),
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
