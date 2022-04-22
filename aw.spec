# -*- mode: python -*-
# vi: set ft=python :

import os
import platform
import subprocess
import aw_core
import flask_restx
import shlex
from pathlib import Path

current_release = subprocess.run(
    shlex.split("git describe --tags --abbrev=0"),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    encoding="utf8",
).stdout.strip()
print("bundling activitywatch version " + current_release)

entitlements_file = Path(".") / "scripts" / "package" / "entitlements.plist"
codesign_identity = os.environ.get("APPLE_PERSONALID")
if codesign_identity is None:
    print("Environment variable APPLE_PERSONALID not set. Releases won't be signed.")

aw_core_path = Path(os.path.dirname(aw_core.__file__))
restx_path = Path(os.path.dirname(flask_restx.__file__))

aws_location = Path("aw-server")
aw_server_rust_location = Path("aw-server-rust")
aw_server_rust_bin = aw_server_rust_location / "target/package/aw-server-rust"
aw_server_rust_webui = aw_server_rust_location / "target/package/static"
aw_qt_location = Path("aw-qt")
awa_location = Path("aw-watcher-afk")
aww_location = Path("aw-watcher-window")

if platform.system() == "Darwin":
    icon = aw_qt_location / "media/logo/logo.icns"
else:
    icon = aw_qt_location / "media/logo/logo.ico"
block_cipher = None

extra_pathex = []
if platform.system() == "Windows":
    # The Windows version includes paths to Qt binaries which are
    # not automatically found due to bug in PyInstaller 3.2.
    # See: https://github.com/pyinstaller/pyinstaller/issues/2152
    import PyQt5

    pyqt_path = os.path.dirname(PyQt5.__file__)
    extra_pathex.append(pyqt_path + "\\Qt\\bin")

aw_server_a = Analysis(
    ["aw-server/__main__.py"],
    pathex=[],
    binaries=None,
    datas=[
        (aws_location / "aw_server/static", "aw_server/static"),
        (restx_path / "templates", "flask_restx/templates"),
        (restx_path / "static", "flask_restx/static"),
        (aw_core_path / "schemas", "aw_core/schemas"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

aw_qt_a = Analysis(
    [aw_qt_location / "aw_qt/__main__.py"],
    pathex=[] + extra_pathex,
    binaries=[(aw_server_rust_bin, ".")],
    datas=[
        (aw_qt_location / "resources/aw-qt.desktop", "aw_qt/resources"),
        (aw_server_rust_webui, "aw_server_rust/static"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

aw_watcher_afk_a = Analysis(
    [awa_location / "aw_watcher_afk/__main__.py"],
    pathex=[],
    binaries=None,
    datas=None,
    hiddenimports=[
        "Xlib.keysymdef.miscellany",
        "Xlib.keysymdef.latin1",
        "Xlib.keysymdef.latin2",
        "Xlib.keysymdef.latin3",
        "Xlib.keysymdef.latin4",
        "Xlib.keysymdef.greek",
        "Xlib.support.unix_connect",
        "Xlib.ext.shape",
        "Xlib.ext.xinerama",
        "Xlib.ext.composite",
        "Xlib.ext.randr",
        "Xlib.ext.xfixes",
        "Xlib.ext.security",
        "Xlib.ext.xinput",
        "pynput.keyboard._xorg",
        "pynput.mouse._xorg",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

aw_watcher_window_a = Analysis(
    [aww_location / "aw_watcher_window/__main__.py"],
    pathex=[],
    binaries=None,
    datas=[
        (aww_location / "aw_watcher_window/printAppStatus.jxa", "aw_watcher_window")
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

# https://pythonhosted.org/PyInstaller/spec-files.html#multipackage-bundles
# MERGE takes a bit weird arguments, it wants tuples which consists of
# the analysis paired with the script name and the bin name
MERGE(
    (aw_server_a, "aw-server", "aw-server"),
    (aw_qt_a, "aw-qt", "aw-qt"),
    (aw_watcher_afk_a, "aw-watcher-afk", "aw-watcher-afk"),
    (aw_watcher_window_a, "aw-watcher-window", "aw-watcher-window"),
)

aww_pyz = PYZ(
    aw_watcher_window_a.pure, aw_watcher_window_a.zipped_data, cipher=block_cipher
)
aww_exe = EXE(
    aww_pyz,
    aw_watcher_window_a.scripts,
    exclude_binaries=True,
    name="aw-watcher-window",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    entitlements_file=entitlements_file,
    codesign_identity=codesign_identity,
)
aww_coll = COLLECT(
    aww_exe,
    aw_watcher_window_a.binaries,
    aw_watcher_window_a.zipfiles,
    aw_watcher_window_a.datas,
    strip=False,
    upx=True,
    name="aw-watcher-window",
)

awa_pyz = PYZ(aw_watcher_afk_a.pure, aw_watcher_afk_a.zipped_data, cipher=block_cipher)
awa_exe = EXE(
    awa_pyz,
    aw_watcher_afk_a.scripts,
    exclude_binaries=True,
    name="aw-watcher-afk",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    entitlements_file=entitlements_file,
    codesign_identity=codesign_identity,
)
awa_coll = COLLECT(
    awa_exe,
    aw_watcher_afk_a.binaries,
    aw_watcher_afk_a.zipfiles,
    aw_watcher_afk_a.datas,
    strip=False,
    upx=True,
    name="aw-watcher-afk",
)

aws_pyz = PYZ(aw_server_a.pure, aw_server_a.zipped_data, cipher=block_cipher)

aws_exe = EXE(
    aws_pyz,
    aw_server_a.scripts,
    exclude_binaries=True,
    name="aw-server",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    entitlements_file=entitlements_file,
    codesign_identity=codesign_identity,
)
aws_coll = COLLECT(
    aws_exe,
    aw_server_a.binaries,
    aw_server_a.zipfiles,
    aw_server_a.datas,
    strip=False,
    upx=True,
    name="aw-server",
)

awq_pyz = PYZ(aw_qt_a.pure, aw_qt_a.zipped_data, cipher=block_cipher)
awq_exe = EXE(
    awq_pyz,
    aw_qt_a.scripts,
    exclude_binaries=True,
    name="aw-qt",
    debug=True,
    strip=False,
    upx=True,
    icon=icon,
    console=False if platform.system() == "Windows" else True,
    entitlements_file=entitlements_file,
    codesign_identity=codesign_identity,
)
awq_coll = COLLECT(
    awq_exe,
    aw_qt_a.binaries,
    aw_qt_a.zipfiles,
    aw_qt_a.datas,
    strip=False,
    upx=True,
    name="aw-qt",
)

if platform.system() == "Darwin":
    app = BUNDLE(
        awq_coll,
        aww_coll,
        awa_coll,
        aws_coll,
        name="ActivityWatch.app",
        icon=icon,
        bundle_identifier="net.activitywatch.ActivityWatch",
        version=current_release.lstrip("v"),
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "CFBundleExecutable": "MacOS/aw-qt",
            "CFBundleIconFile": "logo.icns",
            "NSAppleEventsUsageDescription": "Please grant access to use Apple Events",
            # This could be set to a more specific version string (including the commit id, for example)
            "CFBundleVersion": current_release.lstrip("v"),
            # Replaced by the 'version' kwarg above
            # "CFBundleShortVersionString": current_release.lstrip('v'),
        },
    )
