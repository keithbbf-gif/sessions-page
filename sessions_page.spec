# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
block_cipher = None

# Every file in ui/ except *.bak, including solaro-account.js, tokens.json, and manifest.json.
ui_datas = []
for p in Path("ui").glob("*"):
    if p.is_file() and not p.name.endswith(".bak"):
        ui_datas.append((str(p), "ui"))

desk_modules = [
    "engine", "formats", "desk", "plugin_api", "cosmos_code_hook", "name_model", "csm_core",
    "record", "sheets", "ledger", "ledger_common", "ledger_master", "ledger_menu",
    "ledger_more", "ledger_session", "ledger_calendar", "ledger_glance", "ledger_projects",
    "ledger_sources", "ledger_table", "ledger_toolbar", "proj_titles", "proj_cards",
    "proj_counts", "proj_span", "proj_checkout", "proj_cross", "session_facts",
    "session_chain", "session_keywords", "session_text", "session_preview",
    "session_actions", "session_face", "cal_days", "cal_loose", "cal_month",
    "cal_plans", "cal_priorities", "cal_search",
    "csm_core.errors", "csm_core.error_handlers", "csm_core.tokenctr_bridge",
    "csm_core.tokenctr_types", "csm_core.persist", "csm_core.cosmos_pointer",
    "solaro_core", "solaro_core.account", "solaro_core.mdata",
    "solaro_core.tokenctr", "solaro_core.tokenctr_types",
    "solaro_core.solarolabs", "solaro_core.ui_cache",
]

a = Analysis(
    ["sessions_page.py"],
    pathex=[p for p in [r"V:\a\ai\solaro_core"] if Path(p).is_dir()],
    binaries=[],
    datas=ui_datas,
    hiddenimports=desk_modules,
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
    console=False,
)
