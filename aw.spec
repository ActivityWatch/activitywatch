# -*- mode: python -*-
# vi: set ft=python :

import os

import aw_core
aw_core_path = os.path.dirname(aw_core.__file__)

import flask_restplus
restplus_path = os.path.dirname(flask_restplus.__file__)

block_cipher = None

aw_server_analysis = Analysis(['aw-server/__main__.py'],
    pathex=[],
    binaries=None,
    datas=[
        ('aw_server/static', 'aw_server/static'),

        (os.path.join(restplus_path, 'templates'), 'flask_restplus/templates'),
        (os.path.join(restplus_path, 'static'), 'flask_restplus/static'),
        (os.path.join(aw_core_path, 'schemas'), 'aw_core/schemas')
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher)

aw_qt_analysis = Analysis(['aw_qt/__main__.py'],
    pathex=[] + extra_pathex,
    binaries=None,
    datas=[('resources/aw-qt.desktop', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher)

aw_watcher_afk_analysis = Analysis(['aw_watcher_afk/__main__.py'],
    pathex=[],
    binaries=None,
    datas=None,
    hiddenimports=[
        'Xlib.keysymdef.miscellany',
        'Xlib.keysymdef.latin1',
        'Xlib.keysymdef.latin2',
        'Xlib.keysymdef.latin3',
        'Xlib.keysymdef.latin4',
        'Xlib.keysymdef.greek',
        'Xlib.support.unix_connect',
        'Xlib.ext.shape',
        'Xlib.ext.xinerama',
        'Xlib.ext.composite',
        'Xlib.ext.randr',
        'Xlib.ext.xfixes',
        'Xlib.ext.security',
        'Xlib.ext.xinput',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher)

aw_watcher_window_analysis = Analysis(['aw_watcher_window/__main__.py'],
    pathex=[],
    binaries=None,
    datas=[("aw_watcher_window/printAppTitle.scpt", "aw_watcher_window")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher)

# https://pythonhosted.org/PyInstaller/spec-files.html#multipackage-bundles
# MERGE takes a bit weird arguments, it wants tuples which consists of
# the analysis paired with the script name and the bin name
MERGE(
    (aw_server_analysis, "aw-server", "aw-server"),
    (aw_qt_analysis, "aw-qt", "aw-qt"),
    (aw_watcher_afk_analysis, "aw-watcher-afk", "aw-watcher-afk"),
    (aw_watcher_window_analysis, "aw-watcher-window", "aw-watcher-afk")
)

pyz = PYZ(aw_watcher_window_analysis.pure, aw_watcher_window_analysis.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
    aw_watcher_window_analysis.scripts,
    exclude_binaries=True,
    name='aw-watcher-window',
    debug=False,
    strip=False,
    upx=True,
console=True)
coll = COLLECT(exe,
    aw_watcher_window_analysis.binaries,
    aw_watcher_window_analysis.zipfiles,
    aw_watcher_window_analysis.datas,
    strip=False,
    upx=True,
    name='aw-watcher-window')


COLLECT()