# Handoff — cmSessions — 2026-11-12

Operational. For the next session orchestrator. Do not treat this as a design essay.

Launch behavior below was read from `sessions_page.py` on 2026-11-12. This handoff did not run tests and does not claim any test passed. Counts and exe byte sizes later in this file are older notes. They were not rechecked.

## Where the work is

Live code: `V:\a\ai\COSMOS\builds\sessions-page`

`V:\streams\cmsessions` is an older snapshot. Do not edit it. Do not revive it.

Desktop app the user launches: `C:\Users\Papa\OneDrive\Desktop\CM Sessions.exe`

That file matched `dist_desk\sessions_page.exe` at 16:26 on 2026-11-07 (both 13,757,181 bytes). Two older copies are still on the desktop and are the wrong builds. Do not delete them unless Keith says so:

- `CM Sessions ledger.exe` — 16:10, 13,769,873 bytes
- `CM Sessions sheets.exe` — 15:43, 13,703,646 bytes

Rebuild with:

```
py -3.14 -m PyInstaller --noconfirm --distpath dist_desk sessions_page.spec
```

from the live folder. If `CM Sessions.exe` is open, the copy fails. Close it first, then copy `dist_desk\sessions_page.exe` onto the desktop name.

## Current launch behavior

Read from `V:\A\Ai\sessions-page-teams\docs\sessions_page.py` (`main`, `_launch_gui`, `_serve`, `_open_page`). A grep of `V:\a\ai\COSMOS\builds\sessions-page\sessions_page.py` shows the same frozen no-args branch and `_launch_gui`. This is not a full diff of the two trees.

The Tk desk is not the only window. Code serves `ui/index.html`. The frozen executable with no arguments does not call `desk.main()`.

- Frozen, no arguments (`sys.frozen`, `len(sys.argv) <= 1`, and `main()` called with `argv is None`): `_launch_gui()`. That binds `127.0.0.1` and serves `ui/index.html` (document title "CM Sessions — Full Screen UI"), plus `ui/app.js`, `ui/app.css`, `ui/index_classic.html`, and the three `cmsessions_*.png` files. `sessions_page.spec` sets `console=False` and packs those `ui` files into the exe. A frozen build reads UI from `_MEIPASS`, not from a later edit of the source `ui` folder.
- Ports: 8786 through 8795. If `GET /api/verbs` on a port already lists `find` and `resume`, the new process only opens that page and does not start a second server. A failed bind tries the next port. If every port fails, a message box says `Sessions could not open a local page on ports 8786–8795.`
- The page opens in Microsoft Edge as `msedge.exe --app=http://127.0.0.1:<port>/` when Edge is in Program Files or Program Files (x86). Otherwise it uses `webbrowser.open`. `POST /api/shutdown` stops the loopback server.
- A daemon thread calls `engine.find(limit=250)` unless `CMSESSIONS_NO_PREWARM` or `CMSESSIONS_TEST_MODE` is set.
- `py -3.14 sessions_page.py` with no subcommand does not open a window and does not bind a port. The subcommand is required, so argparse exits with an error. That path is not `desk.main()`.
- `serve` is the same loopback page on one port (default 8786). It opens the page unless `--no-browser` is passed. It does not scan 8786–8795. Unfrozen `serve` reads `ui/` from the source tree on each request, so a browser reload sees HTML, CSS, and JS edits.
- `desk` is the native Tkinter ledger. `desk.main()` does not bind a socket. A second desk sees `Local\cmSessionsDesk` and does not open another Tk window. Use `desk` only when that ledger is the window you mean.

The no-args exe is the Full Screen page. Do not describe the Tk desk as the desktop launch, and do not aim the desktop shortcut at a rule that forbids a browser.

## What this product is

One engine, three shells, in this order:

1. Standalone app first. The no-args exe is the Full Screen page in an Edge app window, or the default browser if Edge is absent. `desk` is the Tk ledger. Neither requires Cosmos.
2. The same engine inside COSMOS, in-process, through `V:\a\ai\COSMOS\cosmos\cosmos_session_tools_kit.py`. Do not edit `cosmos_service.py`, `app.js`, or `header.js`.
3. A plugin for Cosmos Code, through `cosmos_code_hook.py`. Do not copy the engine into `E:\Cosmos_code_repo`. The applied tree `V:\a\ai\COSMOS\cosmos_code` has no `plugins.py`. The snapshot descriptor with an entrypoint is `E:\Cosmos_code_repo\2026-09-30_v2_product_engine\product_cosmos_code\plugins.py`.

cmSessions is not Cosmos and not cDeck. It finds, reads, and resumes local sessions, and the product job is the handoff: carry a transcript into a different installed harness and model. Resume in the same harness is required and is the smaller half. Network and remote sessions are out until the local window and local launch are solid.

## Which drawing wins

Keith's scans override the written design when they conflict.

Master layout: the landscape ledger. Source image: `F:\BROTHER\BRN94DDF88955BC_000643.pdf` page 1 (raster `643-1.png` in the temp scan folder, if it is still there). That sheet is the window.

- Top: Session type (CLI, TUI, Chat), Create summaries, Table view group-by (maker, project, topic), Goals / At-a-glance.
- Columns: RAN IN, time last active, session title, size / token count, session topics, daily summaries (7 days, week, monthly).
- Title color follows the source app. Sub-sessions sit under the title.
- Lower left: the Solaro sun beside the username. Click opens Account and Usage. Usage estimates cost from token counts when a row has them, otherwise from file size divided by 4, using published list prices. It is not a bill. Token Center is not connected.

The portrait drawing labeled TABLE VIEW in red (`F:\BROTHER\BRN94DDF88955BC_000642.pdf`) is a pane inside that ledger, not the frame of the app. The single-session, calendar, and projects drawings are also inside the ledger, not separate pages and not stacked under it all at once.

Written decisions that do not conflict with the scans are in the 2026-11-07 paste in the chat (five jobs: search, list, detail beside a row, status counts, command line; planning is a second view; handoff is the product; no cmSessions subscription; conflict UI is parked). Where that paste says "left rail of filters" and the ledger says "RAN IN", the ledger wins.

## What is actually on screen

`ledger.py` `mount` calls `ledger_master.mount`. `refresh` calls `ledger_master.refresh`.

`ledger_master.py` draws the ledger columns, the header, the daily-summaries column, and the sun menu (`ledger_menu.py`). The center column is a title list. Group by maker, project, or topic re-sorts that list. It does not yet swap the center into the project-card drawing or the calendar drawing. Clicking a title calls `desk._select`. It does not yet replace the center with the single-session drawing.

`desk.py` still builds the older Overview / Sessions / Formats / Recover / Tools frames, then hides them and covers the stage with the ledger. Those actions still exist and are reachable from the Table View pane's More menu when that pane is the one mounted. Confirm which buttons the current `ledger_master.py` header actually shows before telling Keith they are on screen. Create summaries is on the header and does not call a model.

First open: `desk.py` paints a saved index off the UI thread, then `find(enrich=False)`. `read_saved_index` is on `engine.py`. Codex rollout scan is limited to `sessions\` under the Codex home. Do not put a full store walk back on the Tk thread.

## Local find / read / launch

`engine.py` walks the vendor stores. Legal rows are counted and not opened. OpenWork text is in `part.data`. Hermes reads `messages` one session at a time. Codex uses a `.jsonl.zst` sibling when the plain file is gone. Antigravity list comes from `conversation_summaries` and `conversations\*.db`. A missing store is null, not zero.

`engine.resume` launches the known CLI flags. Harnesses with a binary but no resume-id flag start that binary in the project folder. Cline task files that are not `*.messages.json` stay `UNMEASURED`. OpenWork and Cowork stay `OPENWORK_FOCUS` and do not spawn `OpenWork.exe`.

`engine.installed_launchers()` is the list of binaries found on this machine. A harness that is not installed must be hidden, not shown as a dead button. That hide is not finished in the ledger header.

## Tests previously recorded (not re-run)

These counts are notes from 2026-11-07. This handoff did not run them and does not claim they pass.

From `V:\a\ai\COSMOS\builds\sessions-page`, on 2026-11-07, before the last layout rewrite:

- `test_sessions_page.py` 68/68
- `test_desk.py` 21/21
- `test_store_fixes.py` 9/9 then 11/11 after the Antigravity payload test
- `test_record.py` 10/10
- `test_formats.py` ok, 34 records

Re-run `test_desk.py` and `test_sessions_page.py` after the next layout edit. Do not claim they are still green until you have run them.

## Do not

- Do not say the Tk desk is the only window. The no-args exe serves `ui/index.html` on `127.0.0.1`. `desk` is the Tk path, and that path does not bind a port.
- Do not make Table, Session, Calendar, and Projects into separate pages or a left-hand app nav.
- Do not stack all four drawings on one screen at once.
- Do not fork the engine per shell.
- Do not edit `cosmos_service.py`, `app.js`, or `header.js`.
- Do not write analysis into `V:\Ai\BU.MD`. It is operational state for BootUP. This session did not overwrite it.
- Do not write `V:\Research4\BU.MD`.
- Do not auto-delete the older desktop exes.
- Do not add a cmSessions subscription. Token Center is the account, and only when an AI feature is used.
- Do not implement the conflict UI, the unattended mesh, or network sessions yet.

## Next session, in order

The list below is the 2026-11-07 ledger plan. Opening the exe now shows `ui/index.html`, not the Tk desk. Use `sessions_page.py desk` when the check is the Tk ledger.

1. Make the running window match the landscape ledger drawing. Header and six columns and the sun, as above. Check it by opening the window you mean, not by describing the code.
2. Put the Table View drawing inside the session-title column only: column chips, More, search, print, topic list. Do not let that drawing become the window.
3. A clicked row opens the single-session drawing in that same center column: date, start, end, size, tokens, path, keywords, Resume, the harness, the model, session text, session preview. Resume launches the source harness. Hand off and cross-check stay separate. Nothing launches by itself.
4. Group by project shows the project cards in that center column. Calendar shows in that center column. RAN IN, time, size, and daily summaries stay visible.
5. Hide harnesses whose binary is not installed. Carry the indexed transcript on handoff. Record the new session as a child. Do not close the source.
6. Re-run the hermetic tests. Rebuild `dist_desk\sessions_page.exe`. Copy it to `CM Sessions.exe` only after the old process is closed.

## 2026-11-08 — Table View window (642)

Keith chose the 642 TABLE VIEW scan as the main layout, overriding the
landscape-ledger frame. `ledger_master.py` was rewritten to it:

- Nav: Home, DRIVES, SESSIONS, session-tab carousel with < >, Maker
  filter ("Drop Down By Maker"), Group menu (Flat / maker / project /
  topic), Proj / Token count / Cost / TAG column toggles, More menu,
  Create summaries (still does not call a model).
- Red-ruled heads: TOPICS, session Summaries, Proj, Token count, cost $, TAG.
- Body: left list (titles + ages, or drives when DRIVES is scoped),
  center TABLE VIEW, right Daily / Weekly / Monthly / Quarterly, rail
  with SAVE AS, LOAD OPEN, search, calendar, Project folder View, Print.
- Footer: Solaro sun + username (Account and Usage menu), status line,
  "estimates, not a bill" note. Costs use published list prices from
  token counts, else bytes / 4.
- Clicking a left, center, or tab row opens the single-session drawing
  in the center column. Calendar and projects also render in the center.

Rebuilt `dist_desk\sessions_page.exe` and copied it over
`CM Sessions.exe` (13,784,046 bytes). Older desktop copies untouched.
Tests after the edit: test_desk 21/21, test_sessions_page 68/68,
test_store_fixes 11/11, test_record 10/10, test_formats ok. Exe launch
Exe launch checked: process stayed up with a live window, then closed.

## 2026-11-08 — render loop to match (642)

Rendered the window headless-style (visible Tk + screenshots) and
iterated until the pixels matched the sketch:

- Nav overflow pushed Create summaries / More off-screen: session tabs
  moved to their own strip; toggles shortened (Tokens, Cost).
- White voids under the lists: clam theme was applied but a second
  `theme_use("clam")` reset widgets built before it, leaving classic
  white scrollbars. Fix: theme set once in `mount`, then a custom
  dark canvas scrollbar (`_Bar`: drag, trough paging, wheel) replaced
  ttk.Scrollbar entirely. Also added `bordercolor` so tree borders
  stay dark.
- Duplicated headers: removed the global center labels, the tree's
  own headings carry TOPICS columns now; red rule stays above them.
- Center showed 3 of 5 columns: `tk.Text` summary boxes requested 80
  chars and ballooned the right pane. Fixed width 22 cured it.
- Left list is now title + right-aligned age columns.
- Hover tooltips on both lists show the full clipped row text.
- Clicking a row opens the single-session view in the center, verified
  with real data: Resume visible, wrapped metadata, wrapped action
  buttons (`session_actions` reflows), and real transcript text.
- Engine fix (shared, not a fork): openwork preview text lives in
  `part.data`, but `_preview_openwork` only read `message`. It now
  joins part text per message (guarded; DBs without `part` behave as
  before). Verified: 6/6 turns with real text.

Tests after: test_desk 21/21, test_sessions_page 68/68,
test_store_fixes 11/11, test_record 10/10, test_formats ok.
Rebuilt and deployed `CM Sessions.exe` (13,787,656 bytes). Older
desktop copies untouched. Live exe run confirmed up; close it from
the window before the next rebuild.

## 2026-11-08 — item 5: handoff (picker, Hand off, child record)

- Target picker in the session chain row (`Hand off [target ▾]`),
  bound to `app_var`. Lists `engine.installed_launchers()` only —
  uninstalled harnesses are hidden, not shown as dead buttons. The
  source harness stays listed so same-harness Resume can still plan.
  On this machine 11 binaries resolve (grok, claude, codex, cursor,
  gemini, agy, antigravity-ide, hermes, pi, copilot, cline).
- `Hand off` now executes (`desk._on_handoff`): same harness shows
  the resume plan with guidance; a different installed target goes
  through `plan_foreign_launch` → export + bare launch. OPENWORK_FOCUS
  / NEED_LOAD plans display without spawning. Nothing launches by itself.
- `_start_handoff` appends `var/handoffs.jsonl` via
  `engine.record_handoff` (parent id/harness, target, binary, pid,
  carried export path, cwd). "Carry the indexed transcript" = the
  export `.md` path is written into the record and shown. "Record the
  new session as a child" = the pending-child line (child id unknown
  at launch). The source session is never closed.
- Hidden OptionMenu (`_set_app_choices`) filtered the same way.

Tests: 21/21, 68/68, 12/12 (new handoff-record case), 10/10, formats
ok. Render-verified with real data (picker renders, chain row fits).
Deployed as `CM Sessions2.exe` (13,791,423 bytes) per Keith — numbered
names from here on so a running exe never blocks the copy.
`CM Sessions.exe` left untouched.

## TidyUP2 leftovers

`tidyup2_checks.py` and `tidyup2_full.py` look for `V:\Research4\Ai\ROLD\SCARS.md` and `V:\Research4\Ai\BTS_MESH\TOOLS_REGISTRY.json`. Those paths are missing. The live files are `V:\a\ai\BTS_MESH\ROLD\SCARS.md` and `V:\a\ai\BTS_MESH\BTS_MESH\TOOLS_REGISTRY.json`. No new class was appended to SCARS. The checkers were not patched.
