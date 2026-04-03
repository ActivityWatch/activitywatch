# -*- mode: python -*-
# vi: set ft=python :

a = Analysis(
    ['aw-systray-odoo.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['pystray', 'pystray._win32', 'PIL'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['gi', 'psutil', 'win10toast'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='aw-systray-odoo',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)
