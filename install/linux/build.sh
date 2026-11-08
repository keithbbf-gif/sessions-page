#!/usr/bin/env bash
# Build cmsessions_1.0.0_amd64.deb. Linux amd64 only.
# PyInstaller cannot cross-compile; a non-Linux host exits before any .deb.
# cds to the sessions-page tree (parent of install/) so the spec paths resolve.
set -euo pipefail
umask 022

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
OUT_DIR="$SCRIPT_DIR/out"
DEB_NAME="cmsessions_1.0.0_amd64.deb"
OUT="$OUT_DIR/$DEB_NAME"
PARTIAL="$OUT_DIR/.$DEB_NAME.partial"
VENV="$SCRIPT_DIR/.venv"
WORK_DIST="$SCRIPT_DIR/work/dist"
WORK_BUILD="$SCRIPT_DIR/work/build"
STAGE=""

cleanup() {
  if [[ -n "$STAGE" && -d "$STAGE" ]]; then
    rm -rf "$STAGE"
  fi
  if [[ -f "$PARTIAL" ]]; then
    rm -f "$PARTIAL"
  fi
}
trap cleanup EXIT

die() {
  echo "error: $*" >&2
  echo "error: no new .deb was written." >&2
  exit 1
}

if [[ "$(uname -s)" != "Linux" ]]; then
  die "build.sh must run on Linux ($(uname -s) is not). PyInstaller cannot cross-compile an amd64 ELF."
fi

arch=$(uname -m)
case "$arch" in
  x86_64|amd64) ;;
  *) die "this package is amd64 only; uname -m is ${arch}" ;;
esac

if [[ ! -f "$ROOT/sessions_page.spec" || ! -f "$ROOT/sessions_page.py" ]]; then
  die "sessions-page tree not found at ${ROOT} (expected sessions_page.spec)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  die "python3 was not found. Install it: sudo apt-get install -y python3 python3-venv python3-pip python3-tk"
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
  die "dpkg-deb was not found. Install it: sudo apt-get install -y dpkg"
fi

if ! dpkg-deb --help 2>&1 | grep -q -- '--root-owner-group'; then
  die "dpkg-deb has no --root-owner-group. Need Debian 10+ or Ubuntu 18.04+."
fi

cd "$ROOT" || die "cannot cd to ${ROOT}"

PY=""
if [[ ! -x "$VENV/bin/python3" ]]; then
  if ! python3 -m venv "$VENV"; then
    rm -rf "$VENV"
    echo "warning: python3 -m venv failed. Using system python3." >&2
    echo "warning: install python3-venv for an isolated build." >&2
    PY=$(command -v python3)
  else
    PY="$VENV/bin/python3"
  fi
else
  PY="$VENV/bin/python3"
fi

if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
  die "this Python cannot import tkinter. Install python3-tk, remove ${VENV}, and run again."
fi

if ! "$PY" -m PyInstaller --version >/dev/null 2>&1; then
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    die "pyinstaller is missing and pip is not available. Install python3-pip or python3-venv."
  fi
  echo "pyinstaller is missing; installing it with pip"
  if ! "$PY" -m pip install --disable-pip-version-check pyinstaller; then
    if ! "$PY" -m pip install --disable-pip-version-check --break-system-packages pyinstaller; then
      die "could not install pyinstaller"
    fi
  fi
fi

if ! "$PY" -m PyInstaller --version >/dev/null 2>&1; then
  die "pyinstaller is still not runnable"
fi

echo "using python: $PY"
echo "pyinstaller: $("$PY" -m PyInstaller --version)"

rm -rf "$WORK_DIST" "$WORK_BUILD"
mkdir -p "$WORK_DIST" "$WORK_BUILD"

# --distpath and --workpath apply even when the argument is a spec file.
"$PY" -m PyInstaller --noconfirm --clean \
  --distpath "$WORK_DIST" \
  --workpath "$WORK_BUILD" \
  "$ROOT/sessions_page.spec"

BIN="$WORK_DIST/sessions_page"
if [[ ! -f "$BIN" || ! -s "$BIN" ]]; then
  die "pyinstaller did not write a non-empty binary at ${BIN}"
fi
chmod 755 "$BIN"

if command -v file >/dev/null 2>&1; then
  desc=$(file -b "$BIN")
  case "$desc" in
    *ELF*x86-64*|*ELF*x86_64*|*ELF*AMD64*|*ELF*amd64*) ;;
    *) die "built binary is not an amd64 ELF: ${desc}" ;;
  esac
fi

if [[ ! -f "$SCRIPT_DIR/cmsessions" || ! -f "$SCRIPT_DIR/cmsessions.desktop" ]]; then
  die "missing cmsessions wrapper or cmsessions.desktop next to build.sh"
fi

STAGE=$(mktemp -d)
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/local/lib/cmsessions" \
  "$STAGE/usr/local/bin" \
  "$STAGE/usr/share/applications"

install -m 0755 "$BIN" "$STAGE/usr/local/lib/cmsessions/sessions_page"
install -m 0755 "$SCRIPT_DIR/cmsessions" "$STAGE/usr/local/bin/cmsessions"
install -m 0644 "$SCRIPT_DIR/cmsessions.desktop" "$STAGE/usr/share/applications/cmsessions.desktop"

cat > "$STAGE/DEBIAN/control" <<'EOF'
Package: cmsessions
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Depends: libc6
Maintainer: cmSessions <cmsessions@localhost>
Description: Local session finder
 Standalone frozen binary for local harness sessions.
 No Python runtime is required. Depends only on libc6.
EOF
chmod 755 "$STAGE/DEBIAN"
chmod 644 "$STAGE/DEBIAN/control"
find "$STAGE" -type d -exec chmod 755 {} \;

mkdir -p "$OUT_DIR"
rm -f "$PARTIAL"
dpkg-deb --root-owner-group --build "$STAGE" "$PARTIAL"

info=$(dpkg-deb --info "$PARTIAL")
case "$info" in
  *"Architecture: amd64"*) ;;
  *) die "dpkg-deb output is not Architecture amd64" ;;
esac
case "$info" in
  *"Depends: libc6"*) ;;
  *) die "dpkg-deb output does not depend on libc6" ;;
esac

listing=$(dpkg-deb --contents "$PARTIAL")
for path in \
  usr/local/lib/cmsessions/sessions_page \
  usr/local/bin/cmsessions \
  usr/share/applications/cmsessions.desktop
do
  case "$listing" in
    *"$path"*) ;;
    *) die "package is missing ${path}" ;;
  esac
done

if [[ ! -s "$PARTIAL" ]]; then
  die "dpkg-deb wrote an empty package"
fi

mv -f "$PARTIAL" "$OUT"
echo "built ${OUT}"
echo "send this file: ${OUT}"
