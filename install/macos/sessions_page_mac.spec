# -*- mode: python ; coding: utf-8 -*-
# Onedir Mac bundle. This spec lives in install/macos; sources are two levels up.
import os

root = os.path.abspath(os.path.join(SPECPATH, os.pardir, os.pardir))

a = Analysis(
    [os.path.join(root, "sessions_page.py")],
    pathex=[root],
    binaries=[],
    datas=[(os.path.join(root, "ui"), "ui")],
    hiddenimports=["engine", "formats", "desk", "plugin_api", "cosmos_code_hook"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cmSessions",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cmSessions",
)
app = BUNDLE(
    coll,
    name="cmSessions.app",
    bundle_identifier="local.cmsessions",
    version="1.0.0",
    info_plist={
        "CFBundleName": "cmSessions",
        "CFBundleDisplayName": "cmSessions",
        "CFBundleIdentifier": "local.cmsessions",
        "CFBundleExecutable": "cmSessions",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "12.0",
    },
)
