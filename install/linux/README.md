# cmSessions Linux installer

This directory builds a Debian package for cmSessions. It does not contain a prebuilt Linux binary. This package was prepared on Windows. PyInstaller cannot cross-compile a Linux ELF from Windows, so this tree has no amd64 binary and no `.deb`.

The file you send is the package built on a Linux amd64 machine:

```text
install/linux/out/cmsessions_1.0.0_amd64.deb
```

## Build on Debian or Ubuntu (amd64)

Install the build tools. pip needs network access the first time it installs PyInstaller.

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-tk dpkg
```

From the sessions-page directory (the parent of `install`):

```bash
bash install/linux/build.sh
```

`build.sh` changes to that directory itself. From any working directory:

```bash
bash /path/to/sessions-page/install/linux/build.sh
```

The script then:

1. Exits unless the host is Linux and `uname -m` is `x86_64` or `amd64`.
2. Exits if `python3` or `dpkg-deb` is missing.
3. Creates `install/linux/.venv`, or uses system `python3` if `python3 -m venv` fails.
4. Installs PyInstaller if `python3 -m PyInstaller` does not run.
5. Exits if that Python cannot import tkinter (the desk is frozen with it). Install `python3-tk`, delete `install/linux/.venv`, and run the script again.
6. Runs PyInstaller on `sessions_page.spec` in the sessions-page directory.
7. Builds `install/linux/out/cmsessions_1.0.0_amd64.deb` with `dpkg-deb --root-owner-group --build`.

If PyInstaller or `dpkg-deb` is missing and cannot be installed, the script prints an error and does not leave a partial `.deb`. `dpkg-deb` must support `--root-owner-group` (Debian 10+ or Ubuntu 18.04+).

Do not run `build.sh` on Windows. It will refuse, and it cannot produce an ELF here.

## What you send

Send only:

```text
install/linux/out/cmsessions_1.0.0_amd64.deb
```

Do not send this source tree in place of that package.

## Install

On the target Debian or Ubuntu amd64 machine:

```bash
sudo dpkg -i cmsessions_1.0.0_amd64.deb
```

The package `Depends` field is `libc6` only. The frozen binary is the standalone PyInstaller executable. No Python runtime is required to run it.

Installed paths:

- `/usr/local/lib/cmsessions/sessions_page` -- frozen binary
- `/usr/local/bin/cmsessions` -- wrapper script (`install/linux/cmsessions`)
- `/usr/share/applications/cmsessions.desktop` -- menu entry

The menu name is cmSessions. `Exec` is `/usr/local/bin/cmsessions`, `Terminal=false`, `Type=Application`, `Categories=Utility;`. If the menu does not show it yet, log out and back in.

Remove the package with:

```bash
sudo dpkg -r cmsessions
```

That does not delete `~/.local/share/cmsessions`.

## Why the wrapper copies the binary

The frozen program writes `var/` next to the executable. `product_root` is the parent of `sys.executable` after symlink resolution. `/usr/local/lib/cmsessions` is not writable by a normal user, and this package does not change the Python code.

`/usr/local/bin/cmsessions` is a shell script. On first launch it copies `/usr/local/lib/cmsessions/sessions_page` to `~/.local/share/cmsessions/sessions_page` (a real file, not a symlink) and execs that copy with `"$@"`. `var/` is then `~/.local/share/cmsessions/var`. When the installed binary changes, the next launch copies it again, then execs the copy.

## Not built in this tree

No Linux ELF was produced. No `.deb` was produced. Both are created only by `build.sh` on Debian or Ubuntu amd64.
