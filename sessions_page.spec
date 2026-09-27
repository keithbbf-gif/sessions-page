# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ["sessions_page.py"],
    pathex=[],
    binaries=[],
    datas=[("ui", "ui")],
    hiddenimports=["engine"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sessions_page",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
