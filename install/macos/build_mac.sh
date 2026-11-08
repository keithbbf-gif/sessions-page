#!/usr/bin/env bash
# Build dist/cmSessions.app and install/macos/out/cmSessions-1.0.0.dmg.
# Run on a Mac from the sessions-page directory:
#   bash install/macos/build_mac.sh
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on a Mac. PyInstaller cannot cross-compile a macOS app, and hdiutil is not on this OS." >&2
  exit 1
fi

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "hdiutil is missing. It ships with macOS and is required to build the dmg." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is missing. Install Python 3, then run: bash install/macos/build_mac.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# sessions-page root. This file is install/macos/build_mac.sh, so the root is two up.
# The shared spec, from install/, is ../sessions_page.spec (../../ from here).
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
UPSTREAM_SPEC="$ROOT/sessions_page.spec"
MAC_SPEC="$SCRIPT_DIR/sessions_page_mac.spec"
APP="$ROOT/dist/cmSessions.app"
OUT_DIR="$SCRIPT_DIR/out"
DMG="$OUT_DIR/cmSessions-1.0.0.dmg"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -f "$ROOT/sessions_page.py" ]]; then
  echo "Cannot find sessions_page.py under $ROOT. Run this from a sessions-page checkout on a Mac." >&2
  exit 1
fi

if [[ ! -d "$ROOT/ui" ]]; then
  echo "Cannot find $ROOT/ui. The app bundle needs the ui files." >&2
  exit 1
fi

# Windows-shaped means onefile (no COLLECT) or no .app BUNDLE named cmSessions.
# That spec cannot be the Mac one-step app, so use sessions_page_mac.spec.
if [[ -f "$UPSTREAM_SPEC" ]] \
    && grep -q 'exclude_binaries=True' "$UPSTREAM_SPEC" \
    && grep -q 'COLLECT(' "$UPSTREAM_SPEC" \
    && grep -q 'BUNDLE(' "$UPSTREAM_SPEC" \
    && grep -q 'cmSessions.app' "$UPSTREAM_SPEC"; then
  SPEC="$UPSTREAM_SPEC"
else
  SPEC="$MAC_SPEC"
fi

if [[ ! -f "$SPEC" ]]; then
  echo "Spec file is missing: $SPEC" >&2
  exit 1
fi

if [[ ! -x "$VENV/bin/python3" ]]; then
  python3 -m venv "$VENV" || {
    echo "python3 could not create a virtual environment at $VENV." >&2
    exit 1
  }
fi

if ! "$VENV/bin/python3" -c "import PyInstaller" >/dev/null 2>&1; then
  "$VENV/bin/python3" -m pip install "pyinstaller==6.22.3" || {
    echo "pyinstaller is missing and could not be installed into $VENV." >&2
    exit 1
  }
fi

PYI="$VENV/bin/pyinstaller"
if [[ ! -x "$PYI" ]]; then
  echo "pyinstaller is missing. $VENV has no bin/pyinstaller." >&2
  exit 1
fi

cd "$ROOT"
echo "Using spec: $SPEC"
"$PYI" --noconfirm --clean --distpath "$ROOT/dist" --workpath "$ROOT/build" "$SPEC"

if [[ ! -d "$APP" ]]; then
  echo "PyInstaller did not create $APP." >&2
  exit 1
fi

if [[ ! -x "$APP/Contents/MacOS/cmSessions" ]]; then
  echo "cmSessions.app is missing Contents/MacOS/cmSessions." >&2
  exit 1
fi

"$VENV/bin/python3" - "$APP/Contents/Info.plist" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path = Path(sys.argv[1])
with plist_path.open("rb") as handle:
    info = plistlib.load(handle)
expected = {
    "CFBundleName": "cmSessions",
    "CFBundleIdentifier": "local.cmsessions",
    "CFBundleExecutable": "cmSessions",
    "LSMinimumSystemVersion": "12.0",
}
bad = []
for key, value in expected.items():
    if info.get(key) != value:
        bad.append(key + "=" + repr(info.get(key)))
if bad:
    sys.stderr.write("Info.plist is wrong: " + ", ".join(bad) + "\n")
    sys.exit(1)
exe = plist_path.parent / "MacOS" / str(info.get("CFBundleExecutable", ""))
if not exe.is_file():
    sys.stderr.write("CFBundleExecutable is not a file: " + str(exe) + "\n")
    sys.exit(1)
PY

mkdir -p "$OUT_DIR"
STAGE=""
cleanup() {
  if [[ -n "${STAGE:-}" && -d "$STAGE" ]]; then
    rm -rf "$STAGE"
  fi
}
trap cleanup EXIT
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/cmsessions-dmg.XXXXXX")"

if command -v ditto >/dev/null 2>&1; then
  ditto "$APP" "$STAGE/cmSessions.app"
else
  cp -R "$APP" "$STAGE/cmSessions.app"
fi
ln -s /Applications "$STAGE/Applications"

if ! hdiutil create -volname "cmSessions" -srcfolder "$STAGE" -ov -format UDZO "$DMG"; then
  echo "hdiutil failed to create $DMG." >&2
  exit 1
fi

if [[ ! -s "$DMG" ]]; then
  echo "hdiutil did not write $DMG." >&2
  exit 1
fi

echo "Wrote $DMG"
echo "Drag cmSessions onto Applications. No Python is required on that Mac."
