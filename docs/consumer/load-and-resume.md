# Load and Resume

Load reads a session. Resume plans how to continue it, and on some faces it also starts the app. Launch starts an app on this computer. None of them sends the session anywhere.

Which control you pressed matters. The word Load on the full-screen page is not the `load` command.

| What you use | Load | Resume |
|---|---|---|
| `load` and `resume` commands | Reads the session. Prints a count and a header. Does not print the turns. | Plans the session's own app. `--launch` starts it. |
| Desk Sessions view | Same read as the command, shown in the output box. | Shows a plan only. Launch starts it. |
| Full-screen page, `/` | Open / Load opens a tab and asks for a preview. It does not call `load`. | Resume calls `resume` with launch on. |
| Classic page, `/index_classic.html` | Selecting a row asks for a preview. There is no Load button. | Resume shows the command. It does not launch. |

The desk also builds Load, Resume, Launch, Preview, Import, Export, Index, Formats, Check recovery, Restore, Anonymize, Check strip, and Write strip. After the window is built, that stage is covered by the ledger and the left rail is hidden. If you do not see those buttons, use the commands or the full-screen page. Restore asks before it replaces a file. Write strip waits until Check strip has succeeded for that same session.

The desk Sessions view has an App menu. The choices start from the programs found on this machine, and the session's own app stays in the list even when its program was not found. The names the plan understands are grok, claude, codex, cursor, agent, pi, hermes, cline, goose, qwen, copilot, crush, openwork, and cowork. When you select a session, the menu moves to that session's own app. cursor and agent are the same app. openwork and cowork are the same app. You can point the menu at another app. Resume only shows the plan. Launch is what starts something.

## Load

The `load` command reads the session and leaves the source file where it is. It does not rename it, delete it, or rewrite it. The printed result is the id, the turn count, the source hash, and the header. The turns themselves are not in that result.

From the program directory:

```
py -3.14 sessions_page.py load --id <id>
```

If you mean one store instead of the usual folders, add `--store` and the path. Those are the only Load flags. There is no `--out` on Load, and there is no app name. A caller that passes `out` with the `load` action does not get this read. That call writes an import instead. The command cannot do that.

A file larger than 48 MB is refused, except a database the reader queries one session at a time. A damaged jsonl line ends the read there, and you get the turns before that line. sqlite and zstd stay unread where the format index says load is unmeasured. OpenWork's `opencode.db` is the sqlite file Load can read. A Cowork copy inside that database, an id that starts with `ses_cow_`, is refused and is not read. A legal session is refused before the text is opened.

On the full-screen page, Open / Load opens the selected row in a tab and asks for a preview of up to 60 turns, each cut at 3000 characters. It writes nothing. The Resume button in that tab is the real resume, described below. Save As calls export, not load.

On the classic page, selecting a row asks for a preview of up to 6 turns, each cut at 400 characters. That is also what the desk Preview button asks for. The desk does not run that preview just because you clicked the row, unless the ledger has been marked mounted. Legal rows stay closed. The preview writes nothing.

Import writes a copy. Export writes a Markdown copy. Both leave the original file untouched. The desk buttons do the same, with no extra flags.

```
py -3.14 sessions_page.py import --id <id> --out <dir>
py -3.14 sessions_page.py export --id <id> --out <dir>
```

If you omit `--out`, the copy goes under `var\exports`. That `var` folder sits beside the exe when you are using the packaged app. From source it is in the program directory.

## Stores on this computer

OpenWork and Hermes read one session out of a large database. The file size is not the limit. A session stops at 2000 messages. OpenWork text comes from `part.data` (`text` and `type`), joined to the message role. A database with no `part` table still uses `message.data`. Hermes reads `messages.role` and `messages.content`. A Hermes database with no `messages` table stays unmeasured.

Codex keeps a thread whose rollout file is gone, and Load of that row raises `MISSING_FILE`. If that uuid is still on disk as `rollout-*.jsonl` or `rollout-*.jsonl.zst`, the row points at the file and Load reads it. A `.jsonl.zst` file is decompressed for that one session. Protobuf steps inside an Antigravity conversation database are not decoded.

Antigravity and Antigravity CLI list `conversation_summaries`. Load reads readable text out of `steps.step_payload` in `conversations\<id>.db`, up to 40 steps. If that file has no readable text, Load uses the summary preview as one turn. Antigravity IDE lists `conversations\*.db` even when the summary database is missing. A missing preview and an empty payload stay unmeasured. Gemini's walker is still `~/.gemini/tmp`, which is a different store.

The full-screen page draws a token bar from a guess, not from a meter in the file. If the row has no token count, it uses the file size divided by 4, then a price guess. The model name on that row is chosen from the maker label, not read from the session. The status line "Estimates only · Token Center optional" does not change. Those figures are not what Load counted.

Naming from the desk Name button is in [find-and-name.md](find-and-name.md). Load does not call it.

## Resume

On the desk, Resume does not start the app. It shows a plan for the app in the menu ([desk.py](../../desk.py) `desk.plan_resume`, `desk._on_resume`, `desk._paint_plan`). The command line does not take an app name. It always plans the session's own app, and a legal id is refused before a plan is printed ([sessions_page.py](../../sessions_page.py) `sessions_page.main`; [engine.py](../../engine.py) `engine.resume`, `engine._open_hit`). The desk Resume button can still show a plan from the id already on a legal row, because that button does not open the text ([desk.py](../../desk.py) `desk.plan_resume`, `desk._on_resume`). Launch of a legal row is refused ([engine.py](../../engine.py) `engine.resume`, `engine._open_hit`; [desk.py](../../desk.py) `desk._on_launch`).

```
py -3.14 sessions_page.py resume --id <id>
```

`--id` is required. `--launch` is the only other flag ([sessions_page.py](../../sessions_page.py) `sessions_page.main`). There is no flag for another program, and Launch does not add `-p` ([engine.py](../../engine.py) `engine.resume`; [desk.py](../../desk.py) `desk._argv_with_id`, `desk._start_handoff`).

The desk plan is one of these ([desk.py](../../desk.py) `desk.plan_resume`):

- OK. The command continues this session in the app you picked, and the id on that command belongs to that app. A Pi command carries the transcript path, not the short id. A Cline command is only OK when the file name ends in `.messages.json`.
- OPENWORK_FOCUS. The plan is an id to focus in OpenWork. The command list is empty. The program does not start `OpenWork.exe`.
- NEED_LOAD. The session has no id that belongs to the app you picked, or OpenWork has no id to focus. The plan does not put a foreign id on that app's resume flag. It names the app with no session id, and it says to load the turns first. Resume stops there. Launch of another app, other than OpenWork or Cowork, does not use this plan as a resume. It hands the transcript over instead, as described below.
- UNMEASURED. This build has no continue command for that choice. A Cline task that is not a `.messages.json` file stays here when Cline is the session's own app. An app name the plan does not know stays here too.

These are the commands when the plan is OK. The id is the app's own id ([engine.py](../../engine.py) `engine.resume`; [desk.py](../../desk.py) `desk._argv_with_id`).

- Grok: `grok --resume <id>`
- Claude Code: `claude --resume <id>`
- Codex: `codex resume <id>`
- Cursor, also listed as agent: `agent --resume <id>`
- Pi: `pi --session <path to the session file>`
- Hermes: `hermes --resume <id>`
- Cline, only for a `*.messages.json` session: `cline --id <id>`
- Goose: `goose session --resume --session-id <id>`
- Qwen: `qwen --resume <id>`
- GitHub Copilot CLI: `copilot --resume=<id>`
- Crush: `crush --session <id>`

The `resume` command is stricter than the desk menu when the app is not in that list ([engine.py](../../engine.py) `engine.resume`). A Cline task that is not `*.messages.json` is `UNMEASURED`, and the bare `cline` program is not started ([engine.py](../../engine.py) `engine.resume`). For any other app, if a program is installed, the command with no `--launch` is `OK` and the only word is that program ([engine.py](../../engine.py) `engine.resume`, `engine._binary_for`). There is no session id on it. The detail says it would start in the project folder. Gemini, Claude Desktop, and the Antigravity names are in that group when their program is on the machine. If no program is installed, the result is `UNMEASURED`.

The classic Resume button calls `resume` with launch off ([ui/app.js](../../ui/app.js) `onContinue`). It prints the command, or the detail, and does not start anything. It does nothing for a legal row ([ui/app.js](../../ui/app.js) `onContinue`). The Hand off menu on that page only changes a line of text. It does not call the engine ([ui/app.js](../../ui/app.js) `bind`).

The full-screen Resume button calls `resume` with launch on ([ui/index.html](../../ui/index.html) `resumeSelected`; [engine.py](../../engine.py) `engine.resume`). For a Grok row whose guessed token count is at least 180000, the page asks you to confirm before that call ([ui/index.html](../../ui/index.html) `resumeSelected`). The confirm talks about a surcharge. The engine does not charge anything, and it does not know about that 180000 figure ([engine.py](../../engine.py) `engine.resume`). Cancel stays on the page. In the session tab, a guessed Grok count at or above 180000 replaces Resume with Hand off, plus Force Resume, which is the same launch with the confirm skipped ([ui/index.html](../../ui/index.html) `renderSessionView`, `resumeSelected`). A count at or above 170000 only changes the colored bar ([ui/index.html](../../ui/index.html) `renderSessionView`). If the engine returns `LAUNCHED`, the status line shows the process id and the command. If it returns `BINARY_ABSENT`, or any other kind, the page copies a command to the clipboard ([ui/index.html](../../ui/index.html) `resumeSelected`; [engine.py](../../engine.py) `engine.resume`). That command is the engine's argv when one came back. If none came back, the page invents `<maker> --resume <id>`, which is not the plan above ([ui/index.html](../../ui/index.html) `resumeSelected`). `OPENWORK_FOCUS` has an empty command, so the status line is that invented text, and OpenWork is still not started ([engine.py](../../engine.py) `engine.resume`).

## Launch

When the App menu matches the session's own app, Launch is the same as:

```
py -3.14 sessions_page.py resume --id <id> --launch
```

It starts that command in a new console when the program is installed. A found program replaces the first word of the command. Grok is also looked for at `~/.grok/bin/grok.exe`. Cursor may start as `cursor-agent`. It does not pass `-p` ([engine.py](../../engine.py) `engine.resume`). If the program is not installed, Launch does not start anything and the result is `BINARY_ABSENT` ([engine.py](../../engine.py) `engine.resume`). If the working folder stored with the session is missing, Launch does not start ([engine.py](../../engine.py) `engine.resume`). A legal session cannot be launched ([engine.py](../../engine.py) `engine._open_hit`; [desk.py](../../desk.py) `desk._on_launch`). For an app that has no resume id, `--launch` starts the program alone in that folder when the program exists ([engine.py](../../engine.py) `engine.resume`, `engine._binary_for`).

OpenWork and Cowork are focused and not started. Launch returns the id to focus. It does not start `OpenWork.exe`. You focus that id yourself. That is true when OpenWork or Cowork is the session's own app, and it is true when you pick them as the other app ([engine.py](../../engine.py) `engine.resume`; [desk.py](../../desk.py) `desk.plan_resume`, `desk.plan_foreign_launch`).

When you pick a different app on the desk, and that app has no id for this session, Launch exports the transcript and starts that app ([desk.py](../../desk.py) `desk.plan_foreign_launch`, `desk._on_launch`, `desk._start_handoff`). The copy is the same Markdown export as Export, written under `var\exports`, and the original session is left in place ([engine.py](../../engine.py) `engine.export_md`). The other app is started in the session's folder, with no resume id and no `-p`. The command is only the app name ([desk.py](../../desk.py) `desk._bare`, `desk._start_handoff`). Nothing is written into that app's own session store. If that program is not installed, the copy is still written and the app is not started. A legal session is not exported and not started ([engine.py](../../engine.py) `engine.export_md`, `engine._open_hit`).

If that other app already has an id for this row, Launch shows the resume plan and does not start it ([desk.py](../../desk.py) `desk.plan_foreign_launch`, `desk._on_launch`).

The full-screen Hand off button is not that Launch. It calls `handoff` with the words in the picker, such as `Antigravity · Gemini 4 Argon`, exports Markdown under `var\exports`, and appends `var\handoffs.jsonl` ([ui/index.html](../../ui/index.html) `handoffSelected`; [engine.py](../../engine.py) `engine.dispatch`, `engine.export_md`, `engine.record_handoff`). It does not start the other app.
