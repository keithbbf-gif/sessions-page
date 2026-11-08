# Load and Resume

Load reads a session. Resume plans how to continue it. Launch starts an app on this computer. None of them sends the session anywhere.

The desk actions are Load, Resume, Launch, Preview, Import, Export, Index, Formats, Check recovery, Restore, Anonymize, Check strip, and Write strip. Restore asks before it replaces a file. Write strip waits until Check strip has succeeded for that same session.

The desk has an App menu. The choices are grok, claude, codex, cursor, agent, pi, hermes, cline, goose, qwen, copilot, crush, openwork, and cowork. When you select a session, the menu moves to that session's own app. cursor and agent are the same app. openwork and cowork are the same app. You can point the menu at another app. Resume only shows the plan. Launch is what starts something.

## Load

Load reads the session and leaves the source file where it is. It does not rename it, delete it, or rewrite it.

On the desk, Load does that read and shows the result. From `V:\a\ai\COSMOS\builds\sessions-page`:

```
py -3.14 sessions_page.py load --id <id>
```

If you mean one store instead of the usual folders, add `--store` and the path. Those are the only Load flags. There is no `--out` on Load, and there is no app name.

A file larger than 48 MB is refused. A damaged jsonl line ends the read there, and you get the turns before that line. sqlite and zstd stay unread where the format index says load is unmeasured. OpenWork's `opencode.db` is the sqlite file Load can read. A Cowork copy inside that database, an id that starts with `ses_cow_`, is refused and is not read. A legal session is refused before the text is opened.

Preview on the desk is a short read, up to 6 turns, each cut at 400 characters, and it writes nothing. The old `serve` page still does that preview when you select a readable session. It has no Load button.

Import writes a copy. Export writes a Markdown copy. Both leave the original file untouched. The desk buttons do the same, with no extra flags.

```
py -3.14 sessions_page.py import --id <id> --out <dir>
py -3.14 sessions_page.py export --id <id> --out <dir>
```

If you omit `--out`, the copy goes under `var\exports`. That `var` folder sits beside the exe when you are using the packaged app. From source it is in the program directory.

## Stores on this computer

A live census on this PC counted sessions from headers. Message text was not read. The counts were Grok 5314, Claude Code 7257, Codex 1666, Cursor 9, Cowork 666, OpenWork 441, Gemini 28, Hermes 286, and Copilot 31. Legal rows were 135, and those files were not opened. Claude Desktop, Pi, and dsh homes were empty. Cline, Kilo, Roo, Continue, Aider, Goose, Qwen, Amp, OpenHands, Crush, Amazon Q, Factory, Windsurf, and Augment had no store. That census is not one of the hermetic tests.

OpenWork and Hermes read one session out of a large database. The file size is not the limit. A session stops at 2000 messages. OpenWork text comes from `part.data` (`text` and `type`), joined to the message role. A database with no `part` table still uses `message.data`. Hermes reads `messages.role` and `messages.content`. A Hermes database with no `messages` table stays unmeasured.

Codex keeps a thread whose rollout file is gone, and Load of that row raises `MISSING_FILE`. If that uuid is still on disk as `rollout-*.jsonl` or `rollout-*.jsonl.zst`, the row points at the file and Load reads it. A `.jsonl.zst` file is decompressed for that one session. Protobuf steps inside an Antigravity conversation database are not decoded.

Antigravity and Antigravity CLI list `conversation_summaries`. Load reads readable text out of `steps.step_payload` in `conversations\<id>.db`, up to 40 steps. If that file has no readable text, Load uses the summary preview as one turn. Antigravity IDE lists `conversations\*.db` even when the summary database is missing. A missing preview and an empty payload stay unmeasured. Gemini's walker is still `~/.gemini/tmp`, which is a different store.

Naming stays off. It runs only when `CMSESSIONS_NAME` is `1` and `XAI_API_KEY` is set. The call sends the vendor, the session id, a placeholder title, a turn count, and the date. It does not send the transcript or a legal row. The Name button on the desk says "Naming is off." when that is the case. claude.ai IndexedDB is still unmeasured. The stdlib cannot read that leveldb.

A model naming call is not wired. Names stay the local titles in [find-and-name.md](find-and-name.md).

## Resume

Resume does not start the app. On the desk it only shows a plan for the app in the menu. The command line does not take an app name. It always plans the session's own app.

```
py -3.14 sessions_page.py resume --id <id>
```

`--id` is required. `--launch` is the only other flag. There is no flag for another program, and Launch does not add `-p`.

The plan is one of these:

- OK. The command continues this session in the app you picked, and the id on that command belongs to that app. A Pi command carries the transcript path, not the short id. A Cline command is only OK when the file name ends in `.messages.json`.
- OPENWORK_FOCUS. The plan is an id to focus in OpenWork. The command list is empty. The program does not start `OpenWork.exe`.
- NEED_LOAD. The session has no id that belongs to the app you picked, or OpenWork has no id to focus. The plan does not put a foreign id on that app's resume flag. It names the app with no session id, and it says to load the turns first. Resume stops there. Launch of another app, other than OpenWork or Cowork, does not use this plan as a resume. It hands the transcript over instead, as described below.
- UNMEASURED. This build has no continue command for that choice. A Cline task that is not a `.messages.json` file stays here when Cline is the session's own app.

A legal row can still show a plan from the id already on the row. Resume does not open the legal text to do that.

These are the commands when the plan is OK. The id is the app's own id.

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

## Launch

When the App menu matches the session's own app, Launch is the same as:

```
py -3.14 sessions_page.py resume --id <id> --launch
```

It starts that command in a new console when the program is installed. A found program replaces the first word of the command. Grok is also looked for at `~/.grok/bin/grok.exe`. Cursor may start as `cursor-agent`. It does not pass `-p`. If the program is not installed, Launch does not start anything. If the working folder stored with the session is missing, Launch does not start. A legal session cannot be launched.

OpenWork and Cowork are focused and not started. Launch returns the id to focus. It does not start `OpenWork.exe`. You focus that id yourself. That is true when OpenWork or Cowork is the session's own app, and it is true when you pick them as the other app.

When you pick a different app, and that app has no id for this session, Launch exports the transcript and starts that app. The copy is the same Markdown export as Export, written under `var\exports`, and the original session is left in place. The other app is started in the session's folder, with no resume id and no `-p`. The command is only the app name. Nothing is written into that app's own session store. If that program is not installed, the copy is still written and the app is not started. A legal session is not exported and not started.

If that other app already has an id for this row, Launch shows the resume plan and does not start it. A model call is not part of Launch, and it is not part of naming.
