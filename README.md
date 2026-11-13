# Sessions page

This folder is the sessions-page program. The commands below are what `sessions_page.py` does in this tree. Notes that already exist are linked at the end. There is no cmSessions subscription.

## Launch

A frozen exe with no arguments, and the `desk` command, are different starts.

`sessions_page.py` calls `_launch_gui()` only when it is frozen, `main` was given no argv list, and `sys.argv` has no command. That path does not call `desk.main()`. `_launch_gui` uses `127.0.0.1`, ports 8786 through 8795. If this program is already answering `GET /api/verbs` on one of those ports, it opens that page and does not start a second server. Otherwise it serves `ui/` on the first port that binds and opens it. On Windows it tries Microsoft Edge at the usual Program Files paths, with `--app=http://127.0.0.1:<port>/`. If that Edge is not there, it opens the default browser. If every port in that range fails, it reports that Sessions could not open a local page on ports 8786–8795.

The page that path opens is `ui/index.html` (CM Sessions — Full Screen UI). It is the same page as `serve`.

`sessions_page.spec` builds `sessions_page.exe` with the console off. The Windows installer script copies `dist\sessions_page.exe` into `{localappdata}\Programs\cmSessions`. The desktop and Start menu shortcuts point at that exe with no arguments, so a double-click takes the path above. Setup does not start the program. `dist/`, `dist_desk/`, and `dist_new/` are gitignored. The built exe is not in git. Install notes: [install/windows/README.md](install/windows/README.md), [install/linux/README.md](install/linux/README.md), [install/macos/README.md](install/macos/README.md).

The native window is a command:

```
py -3.14 sessions_page.py desk
```

That calls `desk.main()`. It does not bind a port. On Windows a second start sees the mutex `Local\cmSessionsDesk`, shows "Sessions is already open.", and does not open another window. If this Python has no tkinter, the window does not open and the program says so on stderr. `desk` takes no flags. The desk covers its stage with `ledger.mount`, which draws the Table View frame in `ledger_master.py`.

`py -3.14 sessions_page.py` with no subcommand is not a start. The parser requires a command. It does not call `desk.main()` and it does not bind a port.

## Port 8786

`serve` is the loopback page. It binds only `127.0.0.1`. The default port is 8786. It does not try the next port. A port that is taken returns `BIND_FAILED`.

```
py -3.14 sessions_page.py serve
py -3.14 sessions_page.py serve --port 8786
py -3.14 sessions_page.py serve --no-browser
```

Without `--no-browser` it opens the page the same way the frozen start does. It prints a JSON line with `kind` `OK` and `url` `http://127.0.0.1:<port>/`. `POST /api/shutdown` stops that server. The UI in this tree does not call that route. Ctrl+C stops `serve` when it is running in a console.

The frozen no-args start is the path that walks 8786–8795. `serve` stays on the port you named.

`plugin/deck_sessions_page.js` talks only to `http://127.0.0.1:8786`. It is not the desk. See [plugin/REGISTER.md](plugin/REGISTER.md). Routes on that page are in [docs/api.md](docs/api.md).

The desk does not listen. `cosmos_code_hook.py` does not open a port. COSMOS calls this engine in-process. See [docs/integration.md](docs/integration.md) and [docs/consumer/cosmos.md](docs/consumer/cosmos.md).

## Where var/ lives

`engine.var_dir()` is `engine.product_root() / "var"`. It creates the directory.

When the program is frozen, `product_root()` is the parent of `sys.executable` after `Path.resolve()`, which follows symlinks. When it is not frozen, `product_root()` is the directory that contains `engine.py`.

From source, `var/` sits beside `engine.py` in this folder. From a frozen exe, `var/` sits beside that exe, not beside the `engine.py` packed inside the bundle. `test_frozen_root.py` checks both.

The Linux launcher `install/linux/cmsessions` copies the installed binary to `~/.local/share/cmsessions/sessions_page` (a real file, not a symlink) and execs that copy, because `/usr/local/lib/cmsessions` is not writable. `var/` is then `~/.local/share/cmsessions/var`. The Python code does not special-case that path. See [install/linux/README.md](install/linux/README.md).

The engine writes:

- `var/index.jsonl` — default output of `index`, and the saved index `desk` paints before the live walk
- `var/exports` — default directory for `import` and `export` when `--out` is omitted
- `var/stage/<timestamp>/` — `recover --apply` copies the original here, then replaces it from a verified sibling `.bak`. It does not rewrite a corrupt sqlite page in place.
- `var/replaced/<timestamp>/` — an earlier `.ctr.jsonl` and `.ctr.decl.json` moved aside when the same stem is written again
- `var/handoffs.jsonl` — one JSON line per recorded handoff

`var/` is listed in `.gitignore`.

## Commands

From this folder:

```
py -3.14 sessions_page.py find
py -3.14 sessions_page.py import --id <id> --out <dir>
py -3.14 sessions_page.py export --id <id> --out <dir>
py -3.14 sessions_page.py index
py -3.14 sessions_page.py recover --target <file> [--bak <file>] [--apply]
py -3.14 sessions_page.py resume --id <id> [--launch]
py -3.14 sessions_page.py scan --store <path>
py -3.14 sessions_page.py load --id <id> [--store <path>]
py -3.14 sessions_page.py verbs
py -3.14 sessions_page.py formats
py -3.14 sessions_page.py desk
py -3.14 sessions_page.py serve --port 8786
```

`find` accepts `--query`, `--harness`, `--cwd`, and `--limit`. The limit defaults to 200. `load` accepts `--id` and an optional `--store`. `serve` accepts `--port` and `--no-browser`. `desk`, `verbs`, and `formats` take no flags. The same subcommands work on `sessions_page.exe`. Giving that exe no arguments is the frozen launch above, not `desk`.

A missing store is `n: null`, not zero. Legal sessions are counted and their text is not opened. How each harness is stored is the `formats` command, also written in [docs/consumer/formats.md](docs/consumer/formats.md). Find, load, and resume notes are in [docs/consumer/find-and-name.md](docs/consumer/find-and-name.md) and [docs/consumer/load-and-resume.md](docs/consumer/load-and-resume.md). What stays on this machine is in [docs/consumer/safety.md](docs/consumer/safety.md).

## Tests

From this folder, run `py -3.14` and the file name. The checks are the `test_*.py` scripts here, including `test_frozen_root.py` for where `var/` is created and `test_sessions_page.py` for the loopback page on a temporary port. What each file checks is in [docs/testing.md](docs/testing.md). This file does not claim a current pass count.

## Docs in this tree

- [docs/BRIEF.md](docs/BRIEF.md) — product brief
- [docs/api.md](docs/api.md) — loopback routes
- [docs/integration.md](docs/integration.md) — COSMOS and Cosmos Code, in-process, no sessions port
- [docs/testing.md](docs/testing.md) — hermetic checks
- [docs/consumer/README.md](docs/consumer/README.md) — reader notes
- [docs/consumer/install.md](docs/consumer/install.md)
- [docs/consumer/safety.md](docs/consumer/safety.md)
- [docs/consumer/cosmos.md](docs/consumer/cosmos.md)
- [docs/consumer/find-and-name.md](docs/consumer/find-and-name.md)
- [docs/consumer/formats.md](docs/consumer/formats.md)
- [docs/consumer/load-and-resume.md](docs/consumer/load-and-resume.md)
- [HANDOFF.md](HANDOFF.md)
- [JACK_ONBOARDING.md](JACK_ONBOARDING.md)
- [plugin/REGISTER.md](plugin/REGISTER.md)

The consumer notes and [HANDOFF.md](HANDOFF.md) still describe the desk as the packaged start. The launch section above is what `sessions_page.py` in this tree does.
