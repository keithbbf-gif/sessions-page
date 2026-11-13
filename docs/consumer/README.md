# Sessions

Sessions lists chats from the apps you already use, such as Grok, Claude, Codex, and Cursor, and it can show you how to continue one. It does not upload those chats. The desk does not listen on a port ([desk.py](../../desk.py) `desk.main`). The packaged app does: it serves the full-screen page on `127.0.0.1` ([sessions_page.py](../../sessions_page.py) `sessions_page.main`, `sessions_page._launch_gui`, `sessions_page._serve`).

The packaged app opens the full-screen page. The desk is a separate command, and its Sessions buttons sit under the ledger. How to find a session, load it, and resume it, and what the account and settings controls actually do, is [find-and-name.md](find-and-name.md), [load-and-resume.md](load-and-resume.md), and [accounts-and-settings.md](accounts-and-settings.md). The other notes are which apps are in the format index, what stays on this machine, and how COSMOS uses the same engine.

Install is [install.md](install.md). How COSMOS calls this engine, and what is still not in this build, is [../integration.md](../integration.md). The hermetic checks are [../testing.md](../testing.md).

`serve` is the same full-screen page from source. It is not required when you start the packaged app, and the packaged app still binds the port itself.

## Start the window

The finished app is one file, built with the console off:

`V:\a\ai\COSMOS\builds\sessions-page\dist\sessions_page.exe`

That file sits in `dist` next to `sessions_page.spec`. Double-click it, or start it with no arguments. That calls `_launch_gui` ([sessions_page.py](../../sessions_page.py) `sessions_page.main`, `sessions_page._launch_gui`). It opens the full-screen page, `/`, on `127.0.0.1`, starting at port 8786 and trying through 8795 ([sessions_page.py](../../sessions_page.py) `sessions_page._launch_gui`, `sessions_page._serve`). If Edge is installed it opens an app window. Otherwise it opens a browser ([sessions_page.py](../../sessions_page.py) `sessions_page._open_page`). If one of those ports is already this program, a second start only opens that page ([sessions_page.py](../../sessions_page.py) `sessions_page._ours`).

The desk is a different command. A second desk sees the name `Local\cmSessionsDesk` and does not open another window. It tells you Sessions is already open ([desk.py](../../desk.py) `desk.instance_name`, `desk.claim_instance`, `desk.main`).

From `V:\a\ai\COSMOS\builds\sessions-page`:

```
py -3.14 sessions_page.py desk
```

`desk` takes no flags. If this Python has no tkinter, the window does not open and the program says so. A second `desk` is the same mutex. The desk does not bind a port.

`py -3.14 sessions_page.py` with no command is not a start. Only the packaged app opens the page when you give it nothing.

## The page from source

`serve` is the same full-screen page, when you want it from source. It binds `127.0.0.1`. The port defaults to 8786 ([sessions_page.py](../../sessions_page.py) `sessions_page._serve`, `sessions_page.main`). The classic page is `/index_classic.html` on that same server. It is not what `/` shows.

```
py -3.14 sessions_page.py serve
```

Add `--port` only when you want a different port, and `--no-browser` when you do not want a browser tab. The desk does not use this port. The packaged app does not run the `serve` command, but it does call the same server.

## Commands, if you are not using the buttons

Run these from `V:\a\ai\COSMOS\builds\sessions-page`.

```
sessions_page.exe formats
sessions_page.exe verbs
py -3.14 sessions_page.py desk
py -3.14 sessions_page.py formats
py -3.14 sessions_page.py verbs
py -3.14 sessions_page.py find
py -3.14 sessions_page.py load --id <id>
py -3.14 sessions_page.py resume --id <id>
py -3.14 sessions_page.py resume --id <id> --launch
py -3.14 sessions_page.py import --id <id> --out <dir>
py -3.14 sessions_page.py export --id <id> --out <dir>
py -3.14 sessions_page.py index
py -3.14 sessions_page.py recover --target <file>
py -3.14 sessions_page.py recover --target <file> --apply
py -3.14 sessions_page.py scan --store <path>
py -3.14 sessions_page.py serve
```

`formats` and `verbs` take no flags. The same two commands work on `sessions_page.exe`. `find` accepts `--query`, `--harness`, `--cwd`, and `--limit` ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine.find`, `engine.DEFAULT_LIMIT`). The limit defaults to 200, and the desk uses that same limit ([desk.py](../../desk.py) `desk._bg_find`). `load` accepts `--id` and, when you mean one folder instead of the usual places, `--store`. `resume` accepts `--id` and `--launch` only ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine.resume`). `recover` accepts `--target`, an optional `--bak`, and `--apply`. `serve` accepts `--port` and `--no-browser` ([sessions_page.py](../../sessions_page.py) `sessions_page.main`, `sessions_page._serve`). `desk` accepts nothing ([desk.py](../../desk.py) `desk.main`). Those are the flags.

Index, Import, Export, Anonymize, and Write strip write under a `var` folder. When you are running the packaged app, that folder is beside the exe. When you run from source, it is `var` in the program directory. The index file is `var\index.jsonl`. Copies go in `var\exports`. Names in the index are filled in on this computer before they are stored. A legal title stays blank. Import and export leave the original session file where it is. Index does not call a model. The desk Name button is separate.
