# cmSessions for macOS

## Build on a Mac

From the sessions-page directory:

    bash install/macos/build_mac.sh

python3 is required on the build Mac. The script installs PyInstaller into install/macos/.venv if needed, builds dist/cmSessions.app, and writes install/macos/out/cmSessions-1.0.0.dmg.

## What you send

Send that dmg. The person opens it and drags cmSessions onto Applications. No Python is required after the dmg is built.

It is unsigned. Gatekeeper will ask them to open it from the context menu the first time.

## No dmg in this tree

This directory was prepared on Windows. No dmg is here. PyInstaller cannot cross-compile a macOS app, and hdiutil is not available on Windows.
