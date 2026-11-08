# Sessions

Sessions is a window on this computer. It lists chats from the apps you already use, such as Grok, Claude, Codex, and Cursor, and it can show you how to continue one. It does not upload those chats, and the window does not listen on a port.

The window is Blackline Craft. Overview shows drive cards and location cards. Sessions shows search, harness chips, the list, and the detail. The actions are Load, Resume, Launch, Preview, Import, Export, Index, Formats, Check recovery, Restore, Anonymize, Check strip, Write strip, and Name. Name stays off unless naming is turned on. The screenshots in `E:\cmsessions\design` are the face this window follows. The notes beside this file are the same program in writing: how a session is named, how Load and Resume work, which apps are in the format index, what stays on this machine, and how COSMOS uses the same engine with no port.

Install is [install.md](install.md). How COSMOS calls this engine, and what is still not in this build, is [../integration.md](../integration.md). The hermetic checks are [../testing.md](../testing.md).

`serve` is still here, but it is the old loopback page. It is not the way you start.

## Start the window

The finished app is one file, built with the console off:

`V:\a\ai\COSMOS\builds\sessions-page\dist\sessions_page.exe`

That file sits in `dist` next to `sessions_page.spec`. Double-click it, or start it with no arguments. It opens the Sessions desk and does not open a console. It does not bind a port.

A second launch sees the name `Local\cmSessionsDesk` and does not open another window. It tells you Sessions is already open.

From `V:\a\ai\COSMOS\builds\sessions-page` the same window is:

```
py -3.14 sessions_page.py desk
```

`desk` takes no flags. If this Python has no tkinter, the window does not open and the program says so. A second `desk` is the same rule: the window that is already open stays the only one.

`py -3.14 sessions_page.py` with no command is not a start. The packaged app is what opens the desk when you give it nothing.

## The old page

Ask for `serve` only when you want the old browser page. That command still binds `127.0.0.1`. The port defaults to 8786.

```
py -3.14 sessions_page.py serve
```

Add `--port` only when you want a different port, and `--no-browser` when you do not want a browser tab. Quit on that page stops it. The desk does not use this port, and starting the packaged app does not start `serve`.

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

`formats` and `verbs` take no flags. The same two commands work on `sessions_page.exe`. `find` accepts `--query`, `--harness`, `--cwd`, and `--limit`. The limit defaults to 200, and the desk uses that same limit. `load` accepts `--id` and, when you mean one folder instead of the usual places, `--store`. `resume` accepts `--id` and `--launch` only. `recover` accepts `--target`, an optional `--bak`, and `--apply`. `serve` accepts `--port` and `--no-browser`. `desk` accepts nothing. Those are the flags.

Index, Import, Export, Anonymize, and Write strip write under a `var` folder. When you are running the packaged app, that folder is beside the exe. When you run from source, it is `var` in the program directory. The index file is `var\index.jsonl`. Copies go in `var\exports`. Names are filled in before they are stored. A legal title stays blank. Import and export leave the original session file where it is. A model call is not used to name a session.
