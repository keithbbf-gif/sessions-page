# CM Sessions

CM Sessions is the local tool for coding sessions on this machine. It finds them, reads them, and resumes them. The product job is the handoff: carry one transcript into a different installed harness. Resume in the same harness is required, and it is the smaller half.

Someone with no Cosmos install still gets the tool. The same engine is what Cosmos calls in-process, and what Cosmos Code can plug in. One engine. It is not Cosmos, and it is not cDeck. There is no cmSessions subscription.

The command list and the file links are in [README.md](README.md).

## Launch

A frozen `sessions_page.exe` with no arguments calls `_launch_gui()`. It does not call `desk.main()`, and it does listen. It binds `127.0.0.1`, trying port 8786 and then 8787 through 8795. If this program is already up on one of those ports, a later start only opens that page. Otherwise it serves `ui/index.html` and opens it. On Windows that open prefers Microsoft Edge with `--app=`. If Edge is not there, it uses the default browser. If none of those ports bind, it reports that Sessions could not open a local page on ports 8786–8795.

`sessions_page.spec` builds that exe with the console off. The Windows installer copies `dist\sessions_page.exe` to `{localappdata}\Programs\cmSessions` and points the shortcuts at it with no arguments. Setup does not launch it. `dist/`, `dist_desk/`, and `dist_new/` are gitignored. The binaries are not in git.

`py -3.14 sessions_page.py` with no subcommand is not a start. The parser requires a command.

The native window is:

```
py -3.14 sessions_page.py desk
```

That calls `desk.main()`. It does not bind a port. On Windows a second `desk` sees `Local\cmSessionsDesk` and shows "Sessions is already open." If tkinter is missing, the window does not open.

`desk` mounts `ledger_master`. That frame is the Table View: top nav, red-ruled heads, the session list, the center, the summary column, the rail, and the sun beside the username. Session, calendar, and project drawings sit in the center. Create summaries does not call a model. A usage figure on the desk is an estimate from a token count when the row has one, otherwise from file size divided by 4, using the rates in `ledger_master.py`. The full-screen page does not invent that split. It shows a dash when the session has no token count. It is not a bill. Token Center status is the Accounts page, and it stays unavailable until a local TokenCTR URL is set.

## Port 8786

`py -3.14 sessions_page.py serve` serves the same HTML page on `127.0.0.1`. The port defaults to 8786. Pass `--port` for a different one. Pass `--no-browser` to skip opening a browser. `serve` does not walk 8787–8795. That walk is only the frozen no-args start. A taken `serve` port is `BIND_FAILED`.

`POST /api/shutdown` stops the loopback server. The UI in this tree does not call it. The desk does not use this port. `plugin/deck_sessions_page.js` talks to `127.0.0.1:8786` only after someone started `serve` or the frozen page. Routes are in [docs/api.md](docs/api.md).

## Where var/ lives

`engine.var_dir()` is `product_root() / "var"`, and it creates that directory.

From source, `product_root()` is the folder that contains `engine.py`, so `var/` is in this folder. From a frozen exe, `product_root()` is the parent of `sys.executable` after symlink resolution, so `var/` is beside the exe, not inside the packed bundle.

The Linux wrapper copies the binary to `~/.local/share/cmsessions/sessions_page` and execs that copy. `var/` is then `~/.local/share/cmsessions/var`. See [install/linux/README.md](install/linux/README.md).

`var/index.jsonl` is the saved index. The desk paints it on first open when it exists, then walks stores off the window thread. `find(enrich=False)` does not read transcript bodies. `import` and `export` default to `var/exports`. `recover --apply` stages the original under `var/stage/<timestamp>/` and does not rewrite a corrupt sqlite page in place. A replaced transcript pair goes under `var/replaced/<timestamp>/`. Handoff lines append to `var/handoffs.jsonl`. `var/` is gitignored.

## What the engine already does

`engine.py` reads local session stores. A missing store is null, not zero. One bad store is skipped. Legal rows are counted and not opened.

Load works for the stores that were measured on this machine, including Grok, Claude Code, a Codex rollout that is still on disk (plain jsonl or a `.jsonl.zst` sibling), Cursor transcript files, the Cowork catalog, OpenWork (`part.data` text, one session out of a large database), Gemini CLI, Hermes (one session out of `state.db`), and Copilot CLI. Antigravity lists `conversation_summaries` and conversation databases. Readable text is taken from `steps.step_payload`. Protobuf is not decoded as a schema. The format index is the `formats` command and [docs/consumer/formats.md](docs/consumer/formats.md).

`engine.resume` starts the known CLI flags for Grok, Claude Code, Codex, Cursor, Pi, Hermes, Cline `*.messages.json`, Goose, Qwen, Copilot CLI, and Crush. A harness with a binary but no resume-id flag starts that binary in the project folder. Cline task files that are not message logs stay unmeasured. OpenWork and Cowork return an id to focus and do not spawn `OpenWork.exe`.

## Tests

From this folder:

```
py -3.14 test_sessions_page.py
py -3.14 test_desk.py
py -3.14 test_store_fixes.py
py -3.14 test_formats.py
py -3.14 test_record.py
py -3.14 test_frozen_root.py
```

The rest of the `test_*.py` files in this folder are listed in [docs/testing.md](docs/testing.md). Do not treat an older written count as a current pass.

## What is not in this tree

The Cosmos in-process caller is `V:\a\ai\COSMOS\cosmos\cosmos_session_tools_kit.py`. It is outside this repo. `cosmos_code_hook.py` in this folder is the hook those hosts can point at. It does not open a port and does not write a live tree. See [docs/integration.md](docs/integration.md) and [docs/consumer/cosmos.md](docs/consumer/cosmos.md).

Linux and Mac installer notes are [install/linux/README.md](install/linux/README.md) and [install/macos/README.md](install/macos/README.md). No `.deb` and no `.dmg` have been built here. The Windows Inno script is `install\windows\cmSessions.iss`, with [install/windows/README.md](install/windows/README.md). The compiled setup exe is not committed.

Network and remote sessions are out of scope until local launch matches the window you mean to ship. The packaged no-args exe in this tree still opens the loopback page. The desk is `sessions_page.py desk`.

## Docs in this tree

[README.md](README.md), [docs/BRIEF.md](docs/BRIEF.md), [docs/api.md](docs/api.md), [docs/integration.md](docs/integration.md), [docs/testing.md](docs/testing.md), [docs/consumer/README.md](docs/consumer/README.md), [docs/consumer/install.md](docs/consumer/install.md), [docs/consumer/safety.md](docs/consumer/safety.md), [docs/consumer/cosmos.md](docs/consumer/cosmos.md), [docs/consumer/find-and-name.md](docs/consumer/find-and-name.md), [docs/consumer/formats.md](docs/consumer/formats.md), [docs/consumer/load-and-resume.md](docs/consumer/load-and-resume.md), [HANDOFF.md](HANDOFF.md), [JACK_ONBOARDING.md](JACK_ONBOARDING.md), [plugin/REGISTER.md](plugin/REGISTER.md).

[HANDOFF.md](HANDOFF.md) and the consumer notes still say a no-args start opens the desk and binds no port. This file follows `sessions_page.py` at this commit instead.
