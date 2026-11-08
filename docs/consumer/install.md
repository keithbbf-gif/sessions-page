# Install

The program root is `V:\a\ai\COSMOS\builds\sessions-page`.

## Open the window

The window is the desk. It does not listen on a port.

From the program root:

```
py -3.14 sessions_page.py desk
```

`desk` takes no flags. If this Python has no tkinter, the window does not open and the program says so.

The packaged app is `V:\a\ai\COSMOS\builds\sessions-page\dist\sessions_page.exe`. Start it with no arguments. That opens the same desk. It does not open a console, and it does not bind a port.

A second start sees the name `Local\cmSessionsDesk` and does not open another window.

This desk is the plain window. The Blackline Craft screenshots live at `E:\cmsessions\design`. Those pictures are not this face.

`serve` is the old page. It binds `127.0.0.1:8786` only when you ask for it:

```
py -3.14 sessions_page.py serve
```

Starting the packaged app does not start `serve`. Add `--port` only when you want a different port, and `--no-browser` when you do not want a browser tab.

## Windows

The installer is `V:\a\ai\COSMOS\builds\sessions-page\install\windows\out\cmSessions-Setup.exe`.

It installs per user to `{localappdata}\Programs\cmSessions`. The target PC does not need Python. The setup copies the frozen `sessions_page.exe`.

A silent check is:

```
cmSessions-Setup.exe /VERYSILENT /NORESTART /DIR=<folder>
```

The script is `install\windows\cmSessions.iss`. It is 64-bit, it does not ask for an administrator install, and it does not start the program when setup finishes. A desktop shortcut and a Start menu shortcut point at `sessions_page.exe`.

## Linux

`install\linux\build.sh` builds a deb on Debian or Ubuntu. The script exits unless the machine is Linux amd64. No deb is in the tree. This PC has no Linux distro and no Docker, so this machine did not build one. The longer note is `install\linux\README.md`.

## Mac

`install\macos\build_mac.sh` builds a dmg on a Mac. The script exits unless the machine is a Mac. No dmg is in the tree. The longer note is `install\macos\README.md`.
