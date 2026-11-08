# CM Sessions

CM Sessions is the local tool for coding sessions from every AI harness on the machine. It finds them, reads them, and resumes them. The product job is the handoff: carry one transcript into a different installed harness and a different model. Resume in the same harness is required, and it is the smaller half.

Someone with no Cosmos install still gets the full tool. The same engine is what Cosmos calls in-process, and what Cosmos Code can plug in. One engine. It is not Cosmos, and it is not cDeck.

## What you run

The app is a native window. Double-click does not open a browser and does not listen on a port.

From this folder:

```
py -3.14 sessions_page.py
```

That calls `desk.main()`. The frozen build is `dist_desk\sessions_page.exe`, copied for daily use to `CM Sessions.exe` on the desktop. Those binaries are not in git. `dist/` is ignored. `dist_desk\` and `dist_new\` must stay untracked.

`py -3.14 sessions_page.py serve` still serves the older HTML page on `127.0.0.1:8786`. That is not the desktop app.

## The window

The landscape ledger is the window.

Across the top: session type (CLI, TUI, Chat), Create summaries, and group by maker, project, or topic. Goals sits at the right.

The sheet underneath has six columns: RAN IN, time last active, session title, size, session topics, and daily summaries (7 days, week, monthly). A title takes the color of its source app.

The lower left is a sun beside the username. Click it for Account and Usage. Usage estimates cost for a chosen period. It uses a token count when the session has one, otherwise file size divided by 4. Prices are published list rates, blended about three quarters input and one quarter output when the split is unknown. The figure is not a bill. Token Center is not connected.

The Table View drawing, the single-session drawing, the calendar, and the project cards are meant to sit inside this ledger. They are not separate apps and not a left-hand nav. That inner placement is not finished. Group by re-sorts the title list. Create summaries does not call a model.

## What the engine already does

`engine.py` reads local session stores. A missing store is null, not zero. One bad store is skipped. Legal rows are counted and not opened.

Load works for the stores that were measured on this machine, including Grok, Claude Code, a Codex rollout that is still on disk (plain jsonl or a `.jsonl.zst` sibling), Cursor transcript files, the Cowork catalog, OpenWork (`part.data` text, one session out of a large database), Gemini CLI, Hermes (one session out of `state.db`), and Copilot CLI. Antigravity lists `conversation_summaries` and conversation databases. Readable text is taken from `steps.step_payload`. Protobuf is not decoded as a schema.

`engine.resume` starts the known CLI flags for Grok, Claude Code, Codex, Cursor, Pi, Hermes, Cline `*.messages.json`, Goose, Qwen, Copilot CLI, and Crush. A harness with a binary but no resume-id flag starts that binary in the project folder. Cline task files that are not message logs stay unmeasured. OpenWork and Cowork return an id to focus and do not spawn `OpenWork.exe`. A harness that is not installed should be hidden. That hide is not finished on the ledger header.

The first open paints a saved index if `var/index.jsonl` exists, then walks the stores off the window thread. `find(enrich=False)` does not read transcript bodies. The Codex file scan stays under `sessions\`.

## Tests

From this folder:

```
py -3.14 test_sessions_page.py
py -3.14 test_desk.py
py -3.14 test_store_fixes.py
py -3.14 test_formats.py
py -3.14 test_record.py
```

On 2026-11-07, before the last layout pass, those were green: 68, 21, 11, 34, and 10. Re-run them after a layout edit before calling them green.

## What is not in this tree

The Cosmos in-process caller is `V:\a\ai\COSMOS\cosmos\cosmos_session_tools_kit.py`. It is outside this repo. The Cosmos Code snapshot descriptor is on `E:\`. `cosmos_code_hook.py` in this folder is the hook those hosts can point at. It does not open a port and does not write a live tree.

Linux and Mac installer scripts are under `install\`. No `.deb` and no `.dmg` have been built here. The Windows Inno script is `install\windows\cmSessions.iss`. The compiled setup exe is not committed.

Network and remote sessions are out of scope until the local window and local launch are solid. There is no cmSessions subscription.
