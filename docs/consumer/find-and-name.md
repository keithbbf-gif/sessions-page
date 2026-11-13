# Places, Find, and names

Three faces can list sessions. They do not all search the same way.

- The full-screen page is what a packaged app opens when you start it with no arguments. It is `ui/index.html`, served at `/` and `/index.html`. Scan asks the engine to walk.
- The classic page is `/index_classic.html`. It is not the page the packaged app opens. Its script is `/app.js`.
- The desk is `py -3.14 sessions_page.py desk`. It does not bind a port ([desk.py](../../desk.py) `desk.main`). `find` on the command line is the same walk, with no window ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine.find`).

There is no other list page. `POST /api/run` is how both pages ask for a walk. The body is `{ "action": "find", ... }`.

## Places

The desk Overview shows drive cards, then location cards. A drive card is the letter, the label, the kind, and whether the volume answered. A location card is one default session folder, present or absent, with its path when it is here. Cards do not count sessions. A count stays empty until Find runs. The program reads drive letters and labels. It does not walk every file on the drive to draw the cards.

Select a drive card to show sessions whose path is on that drive, and to clear the app filter. Select a location card to show that app only, and to clear the drive filter. On the Sessions view, All clears the app filter. A drive chip with × clears the drive filter. Refresh reads the places again and runs Find again.

The full-screen page asks `GET /api/places` after a scan and draws a card for each drive that answered. A folder card is a location whose path is on that drive. Clicking a drive switches cards. Double-clicking a folder card only changes the status line. It does not open the folder, and it does not filter the session list.

A place with no documented folder stays absent. Factory, Windsurf, and Augment are in that group on purpose. Amazon Q is absent unless `AMAZONQ_HISTORY` points at an export you already have. The program does not treat `~/.aws/amazonq` as a transcript store.

Shortcuts are not followed. A linked folder is not used as the store.

The format index also names some folders the program does not walk. Those are listed in [formats.md](formats.md). They do not appear as counted places.

## Find

Find counts sessions from headers, then fills titles for the rows it is about to show ([engine.py](../../engine.py) `engine.find`, `engine._enrich`). It does not open the text of a legal session ([engine.py](../../engine.py) `engine.is_legal`, `engine._enrich`). The match is a case-insensitive piece of the id, the vendor id, the title, the working folder, or the app name ([engine.py](../../engine.py) `engine._match`).

```
py -3.14 sessions_page.py find --query "something" --harness claude --limit 200
```

`--harness` is the family name, such as `claude` or `grok`, or that family's prefix, such as `cc`. `--cwd` keeps rows whose working folder is that path or contains it ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine.find`, `engine._match`). There is no `--drive` flag ([sessions_page.py](../../sessions_page.py) `sessions_page.main`). The drive filter is the drive you selected on the desk ([desk.py](../../desk.py) `desk._bg_find`; [engine.py](../../engine.py) `engine._on_drive`). The page can pass `drive` on `POST /api/run` ([engine.py](../../engine.py) `engine.dispatch`), but neither page does ([ui/index.html](../../ui/index.html) `loadLiveSessions`; [ui/app.js](../../ui/app.js) `find`).

The command and the desk show up to 200 sessions, newest first ([engine.py](../../engine.py) `engine.find`, `engine.DEFAULT_LIMIT`). The command fills blank titles on those 200 ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine._enrich`). The desk does not ([desk.py](../../desk.py) `desk._bg_find`). A blank title on the desk stays blank until something else names it. The full-screen page asks for 250 and does fill titles ([ui/index.html](../../ui/index.html) `loadLiveSessions`; [engine.py](../../engine.py) `engine.dispatch`). The classic page asks for 200 and does fill titles ([ui/app.js](../../ui/app.js) `find`). `limit` on `POST /api/run` may be from 1 to 2000 ([engine.py](../../engine.py) `engine.dispatch`, `engine._bounded_int`). The `fresh` flag must be true or false ([engine.py](../../engine.py) `engine.dispatch`). The walk ignores it and reads the stores again either way ([engine.py](../../engine.py) `engine._live_load`). Remembered rows are only so a later Load can find an id. They are not the answer to Find ([engine.py](../../engine.py) `engine._live_load`).

While the desk walk runs, the list can show `var\index.jsonl` from the last Index, with the line "Showing the last index. Refreshing…" ([engine.py](../../engine.py) `engine.read_saved_index`; [desk.py](../../desk.py) `desk._offer_saved`, `desk._apply_saved`). The live walk replaces that list ([desk.py](../../desk.py) `desk._bg_find`, `desk._apply_find`). When you are running the packaged app, `var` is the folder beside the exe. From source it is `var` in the program directory.

The full-screen page starts with sample rows that are not your sessions. A scan replaces them only when Find returns at least one row. If the scan returns none, or the page cannot reach `/api/run`, those samples stay. The status line may say it is using a cached ledger. It did not read the index file.

Search on the full-screen page does not call Find again ([ui/index.html](../../ui/index.html) `onSearch`). The toolbar search and the Sessions-view filter hide rows already on screen. They look at the title, topic, summary, project, tags, maker name, status, folder, and id. The two boxes are not kept in step. Closing search clears the toolbar box only. Maker and harness checkboxes filter that same on-screen list. You cannot clear the last maker. The harness menu lists Claude Code, Antigravity, OpenWork, Hermes, Codex, and Grok CLI. Select All also includes a second Grok key that the menu does not draw. An app the page does not recognize is labeled Claude Code.

Search on the classic page submits Find again ([ui/app.js](../../ui/app.js) `bind`, `find`). The command bar copies its text into that search box and submits the same Find. Vendor and status checkboxes, and a project click, filter the rows already returned. They do not walk again. A row updated in the last 15 minutes is shown as active. Anything else is idle, unless the row's own status, state, or stream already says active, idle, or crashed. Grouping only reorders that list.

A missing store is not zero. Its count is null, and the place stays absent. One bad store is skipped. That family's count is null, and its status is the error, not a number. The other apps are still counted ([engine.py](../../engine.py) `engine.find`).

`scan` looks at one store you name, and only that store:

```
py -3.14 sessions_page.py scan --store <path>
```

If that path is not a known kind of store, the count is null.

Legal sessions are still counted. Their title and folder are blank, and the row is labeled as a legal session. The count line says how many were left closed ([engine.py](../../engine.py) `engine.find`; [desk.py](../../desk.py) `desk._show_found`). A session is legal when its stream is named legal, or when its path, working folder, or title contains `\legal\`, `p:\legal`, `v:\ai\legal`, or `\abraxas\`. A path that ends in `\legal` is treated the same way ([engine.py](../../engine.py) `engine.is_legal`). Find does not read that transcript ([engine.py](../../engine.py) `engine._enrich`).

Claude Code listing is one project folder deep. It does not open nested subagent folders. A session file sitting directly in the projects folder is still listed. A project folder whose name contains `claude-probe` is skipped and is not listed.

## How a session gets its name

Local naming is what Find does when it fills titles. The engine has no name command. The full-screen page and the classic page have no Name button. On the classic page, Create summaries says a model summary is not part of this pass and uses the title and project already on the row.

The name Find stores is chosen on this computer, in this order, and only for the rows on screen when titles are being filled:

1. A title the app already stored. That is a Grok summary title, a Cowork or database title, a Cursor header title, or another title already on the row. If that title is present, it is kept.
2. For a Claude or Claude Desktop jsonl whose title is still blank, the head of the file. An ai-title line stores its name in `aiTitle`. That local automatic name wins over the first user line, and it wins over a custom title on the same line. A custom-title line can also supply a custom title, title, or summary.
3. If the title is still blank, a short header sniff for a custom title, a generated title, a title, or a summary.
4. If the title is still blank and the file is jsonl, the first user line, cut at 80 characters. The program stops looking after about 256 KB. It does not read the rest of a long file just to name it.
5. Otherwise the title stays blank.

When the title is blank, the desk list shows the id. The id is not stored as the title. A legal row stays blank even if a name was found, and the id is what you see. The full-screen page invents a label from the maker and the first characters of the id when the title is blank. That label is not written back.

Index on the desk uses this same naming and writes the name into `var\index.jsonl`. A legal title is stored blank.

The desk Name button is separate. It tries to import `name_model` and call `maybe_name`. The Tools page says that stays off unless `CMSESSIONS_NAME` is `1` and `XAI_API_KEY` is set, and that it sends a header, not the transcript. The call the button builds is the vendor id, the session id, the app, the title `untitled`, the date, and the turn count if Preview already ran for that same id. It does not put the transcript in that call. If the module is missing, the function is missing, or the answer is empty, the desk says "Naming is off." This build's engine does not check those two settings itself.

The id you see is the app's own id with a short prefix, such as `grok-`, `cc-` for Claude Code, `cdx-` for Codex, and `cur-` for Cursor. The prefix is not a title.
