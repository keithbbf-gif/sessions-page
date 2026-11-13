# Formats

This is the format index. The program keeps the same rows in `formats.py` under the name `cmsessions-format-index/1`. It does not walk a store to build this list. The desk Formats button shows each family with its load state and resume line. `sessions_page.exe formats` and `py -3.14 sessions_page.py formats` print the same index. That command takes no flags.

Each family is measured, unmeasured, or absent. Measured means a known transcript can be loaded. Unmeasured means the family is recognized, or counted, but the import stays unread except where the note below says a text file can load. Absent means there is no home, and the count stays null, not zero. Resume is the command shape, or `OPENWORK_FOCUS`, `UNMEASURED`, or `POINTER` ([formats.py](../../formats.py) `formats.CATALOG`, `formats.catalog`). A found program replaces only the first word of a command ([engine.py](../../engine.py) `engine.resume`; [desk.py](../../desk.py) `desk._argv_with_id`). Resume does not pass `-p` ([engine.py](../../engine.py) `engine.resume`; [desk.py](../../desk.py) `desk._argv_with_id`).

Legal rows are counted and their text is not opened. A file over 48 MB is not loaded. A missing store is null, not zero. One bad store is skipped.

## Grok

Load is measured. Resume is `grok --resume <vendor_id>`.

The home is `GROK_SESSIONS` or `%USERPROFILE%\.grok\sessions\<folder>\summary.json` beside `chat_history.jsonl`. The header is the id in `summary.json`, or else the folder name, plus the folder and the title. The jsonl is counted from its size and is not read to list the session. The title is `generated_title`, `session_summary`, or `title`, and root fields win over a nested info object. The body is `chat_history.jsonl`. The walk skips `node_modules` and `.git`. A legal path or folder is counted with the title and folder blanked, and the body is not opened.

## Claude Code

Load is measured. Resume is `claude --resume <vendor_id>`.

The home is `%USERPROFILE%\.claude\projects\<cwd-slug>\<uuid>.jsonl`. `CLAUDE_CONFIG_DIR` replaces the `.claude` root. The header is the file name, size, and time. The project folder name is only a legal gate. The title starts blank at scan. Title fields are `aiTitle`, `customTitle`, `title`, and `summary`. An ai-title line stores the name in `aiTitle`. The sniff still reads a custom title, title, or summary, then the first user text. The body is jsonl turns. Scan does not open the file. Listing is one project directory deep and does not descend into nested subagents. A uuid jsonl sitting on the projects root is also listed. A project folder whose name contains `claude-probe` is not listed. Legal rows stay blank and are not opened. Legal is not its own format.

## Codex

Load is measured. Resume is `codex resume <vendor_id>`.

The home is `CODEX_HOME` or `%USERPROFILE%\.codex`. The header is `state_<digits>.sqlite` threads, with id, folder, title, and rollout path. Rollout files still on disk are listed too, including a `rollout-*.jsonl.zst` when the plain jsonl is gone. The body is jsonl `response_item` role and content. A session meta line is not a turn. Any path part named `archived` is skipped. A thread whose file is gone stays on the list, and Load raises `MISSING_FILE`. The vendor id is the threads id, or the uuid in the rollout file name.

## Cursor

Load is measured. Resume is `agent --resume <vendor_id>`.

The home is `CURSOR_HOME` or `%USERPROFILE%\.cursor`. The header is `chats\<workspace>\<uuid>\meta.json`, else `store.db`, plus `projects\<workspace>\agent-transcripts\<uuid>\<uuid>.jsonl`, plus composer headers in `%APPDATA%\Cursor\User\globalStorage\state.vscdb` when the root is the real `.cursor` home. The title is `meta.json` or the composer value's title or name. Transcripts use the Claude header reader, which keeps `aiTitle` when an ai-title line has that field. Title fields on the index row are `title`, `name`, `customTitle`, and `summary`. The body of an agent transcript uses the Claude turn reader. `meta.json` is a header. `store.db` and `state.vscdb` have no transcript adapter, and importing them stays unmeasured. Composer headers stay unarchived and non-subagent, and the body is not read. The first word of the command may be `cursor-agent`.

## Cowork

Load is measured. Resume is `OPENWORK_FOCUS`.

The home is `COWORK_CATALOG` or `%USERPROFILE%\OpenWork Chat\cow_sessions\COW_SESSION_CATALOG.json` plus `ordered_transcripts`. The header is a catalog row: session id or seq, filename, stream, and title. The markdown is not required to count. The title is the catalog title, and it is blank when the stream is legal. The body is ordered-transcript markdown split on a heading, or a jsonl read. The alias `opencode_id` is `ses_cow_` plus the seq padded to three digits when seq is an integer or digits. Those ids are not OpenWork rows. A legal stream blanks the title and folder, and the body is not opened. A missing transcript points at the catalog and loads no turns. Resume returns the id and does not spawn `OpenWork.exe`.

## OpenWork

Load is measured. Resume is `OPENWORK_FOCUS`.

The home is `OPENCODE_DB`, else the first real file among `%USERPROFILE%\.local\share\opencode\opencode.db`, `%LOCALAPPDATA%\opencode\opencode.db`, and `%APPDATA%\opencode\opencode.db`. The header is sqlite session id, title, and directory. Ids starting with `ses_cow_` are skipped. The title is `session.title`. The body is sqlite message data, ordered by time. A `ses_cow_` id forced through Load raises a refusal and is not read. Resume returns the id and does not spawn `OpenWork.exe`. Migrate and rebind stay closed.

## Claude Desktop

Load is measured. Resume is `UNMEASURED`.

The home is `CLAUDE_DESKTOP_SESSIONS` or `%APPDATA%\Claude\local-agent-mode-sessions\*.jsonl`. The header is a recursive jsonl, and the vendor id is the filename stem. The title is a first-kilobyte sniff of `customTitle`, `generated_title`, `title`, or `summary`. A blank title is then filled the same way as Claude Code, including `aiTitle` on an ai-title line. The body uses the Claude turn reader. The program does not launch Claude Desktop. Claude project, artifact, and scheduled folders are places, not session formats.

## Gemini

Load is measured. Resume is `UNMEASURED`.

The home is `GEMINI_SESSIONS`, else `(GEMINI_CLI_HOME or %USERPROFILE%)/.gemini/tmp/<project>/chats/*.{json,jsonl}`. The file stem is the id. The folder is `<project>\.project_root`. `sessions.json` is skipped. The title is blank at list, then a jsonl sniff of `customTitle`, `generated_title`, `title`, or `summary`. The body is jsonl turns, or json `history`, `messages`, or `conversation`. This is Gemini CLI tmp, not `~/.gemini/antigravity`, `antigravity-ide`, or `antigravity-cli`. An internal session id is not the vendor id. Json without those turn keys stays unmeasured.

## Hermes

Load is unmeasured. Resume is `hermes --resume <vendor_id>`.

The home is `HERMES_STATE`, else `HERMES_HOME\state.db`, else `%USERPROFILE%\.hermes\state.db`, else `%LOCALAPPDATA%\hermes\state.db`, and also `profiles\*\state.db` beside that home. The header is sqlite session id, title or display name, folder, and last activity. The title is `sessions.title`, else `display_name`. The body on record is the sqlite session row only. Hidden rows are dropped when that column exists. Transcript import stays unmeasured. When the home is a known candidate, every candidate database is read once.

## Cline

Load is measured. Resume is `cline --id <vendor_id>`.

The home is `CLINE_SESSION_DATA_DIR` or `CLINE_TASKS`, else the first real peer: editor globalStorage tasks for `saoudrizwan.claude-dev` or `cline.cline`, JetBrains globalStorage tasks, and `%USERPROFILE%\.cline\data\sessions` or `tasks`. The header is the task folder name, or the parent of `<id>.messages.json`. The title is `title`, `task`, or `name` from task metadata or `<id>.json`. The body is `api_conversation_history.json` or `<id>.messages.json`. Resume is unmeasured unless the path ends with `.messages.json`. Editor hosts are Code, Code - Insiders, Cursor, Windsurf, VSCodium, Cline, and Kilo. `CLINE_DATA_DIR` and `CLINE_DIR` add `data\sessions` and `data\tasks`.

## Kilo Code

Load is measured. Resume is `UNMEASURED`.

The home is `KILO_TASKS`, else editor globalStorage `kilocode.kilo-code\tasks`, `%USERPROFILE%\.kilocode\cli\global\tasks`, or `%USERPROFILE%\.kilocode\globalStorage\kilocode.kilo-code\tasks`. The header is the task folder name. The file is `api_conversation_history.json`. The title is `title`, `task`, or `name` in task metadata. The body is that history file. This is the same task-folder reader as Cline. There is no messages.json walker and no resume command.

## Roo Code

Load is measured. Resume is `UNMEASURED`.

The home is `ROO_TASKS`, else editor or JetBrains globalStorage `rooveterinaryinc.roo-cline\tasks`, else `%USERPROFILE%\.roo\tasks`. The header is the task folder name. The file is `api_conversation_history.json`. The title is `title`, `task`, or `name` in task metadata. This is the same task-folder reader as Cline. There is no resume command.

## Pi

Load is measured. Resume is `pi --session <path>`.

The home is `PI_CODING_AGENT_SESSION_DIR` or `PI_SESSIONS` or `%USERPROFILE%\.pi\agent\sessions`. The header is a recursive jsonl, and the vendor id is the filename stem. The title is a first-kilobyte sniff of `customTitle`, `generated_title`, `title`, or `summary`. The body is jsonl, using role and content or text. Resume passes the transcript path, not the vendor id.

## GitHub Copilot CLI

Load is measured. Resume is `copilot --resume=<vendor_id>`.

The home is `COPILOT_SESSION_STATE` or `%USERPROFILE%\.copilot\session-state\*\events.jsonl`. The header is `session.start` session id, else the directory name. The folder is `data.context.cwd`. The title is blank at list. There is no dedicated title field at list time. A later pass may still sniff a jsonl header. The body is `events.jsonl` user, assistant, system, and tool-start lines. The directory name is not the id when session start carries one.

## Continue

Load is measured. Resume is `UNMEASURED`.

The home is `CONTINUE_SESSIONS` or `CONTINUE_GLOBAL_DIR\sessions` or `%USERPROFILE%\.continue\sessions\*.json`. The header is one json file. The id is `sessionId` or `id`, else the stem. `sessions.json` is skipped. The title is the json title. Title fields are `title`, `sessionId`, and `workspaceDirectory`. The folder is `workspaceDirectory`. The body is json `history`, `messages`, or `conversation`. A json object without those turn keys stays unmeasured. There is no resume command.

## Aider

Load is unmeasured. Resume is `UNMEASURED`.

The home is `AIDER_CHAT_HISTORY_FILE` only. The header is that one file. The vendor id is the filename, including its extension. There is no title field. The history file is counted and not parsed. There is no global session directory. The default home is empty, so the count stays null until that setting is set. Markdown import stays unmeasured.

## Goose

Load is unmeasured. Resume is `goose session --resume --session-id <vendor_id>`.

The home is `GOOSE_SESSIONS`, else `sessions.db` under `GOOSE_PATH_ROOT\data\sessions`, `%APPDATA%\Block\goose\data\sessions`, or `%USERPROFILE%\.local\share\goose\sessions`. The header is sqlite session id, name or description, working folder, and updated time. Hidden and subagent rows are skipped. The title is the sqlite name, else the description. A legacy jsonl uses the header sniff. The body on record is the sqlite session row. Legacy `*.jsonl` files are used only when no `sessions.db` is present. Database import stays unmeasured. A jsonl directory is the legacy shape and can load. The program also checks the macOS Block goose database paths.

## Qwen

Load is measured. Resume is `qwen --resume <vendor_id>`.

The home is `QWEN_SESSIONS` or `%USERPROFILE%\.qwen\projects\<cwd>\chats\*.jsonl`. The header is the same chats walker as Gemini. The vendor id is the filename stem. `sessions.json` is skipped. The title is blank at list, then a jsonl sniff of `customTitle`, `generated_title`, `title`, or `summary`. The body is jsonl turns, or json `history`, `messages`, or `conversation`. The folder may come from a `.project_root` two parents above the chat file.

## Amp

Load is measured. Resume is `UNMEASURED`.

The home is `AMP_THREADS_DIR` or `AMP_SESSIONS` or `(XDG_DATA_HOME or %USERPROFILE%\.local\share)\amp\threads\*.json`. The header is one json file. The id is `id`, else the stem. The title is the json title. The body is json `history`, `messages`, or `conversation`. No folder is recorded. Json without those turn keys stays unmeasured. There is no resume command.

## OpenHands

Load is unmeasured. Resume is `UNMEASURED`.

The home is `OPENHANDS_SESSIONS` or `%USERPROFILE%\.openhands\conversations\*\base_state.json`. The header is `base_state.json` id or conversation id, else the parent folder. `conversations\*\base_state.json` is also read. The title is the title in that file. Title fields are `title`, `id`, `conversation_id`, and `workspace`. The body on record is the header only. The events directory is not read. The folder is `workspace`, else `cwd`. Import stays unmeasured unless the json has `history`, `messages`, or `conversation`. There is no resume command.

## Crush

Load is unmeasured. Resume is `crush --session <vendor_id>`.

The home is `CRUSH_SESSIONS` or `(XDG_DATA_HOME or %USERPROFILE%\.local\share)\crush\projects.json`. The header is `projects.json` path and data dir, then `crush.db` session id and title. The title is `sessions.title`. The body on record is the sqlite sessions row, and `parent_session_id` must be null. The database is `<data_dir>\crush.db`, else `<project>\.crush\crush.db`. Import stays unmeasured. The resume folder is the project path.

## Amazon Q

Load is unmeasured. Resume is `UNMEASURED`.

The home is `AMAZONQ_HISTORY` only. The header is `q-dev-chat-*.md`, `q-dev-chat-*.html`, or `q-dev-chat-*.json`. The vendor id is the stem. There is no title field. Markdown and html are not parsed. The default home is empty, so the count stays null. `~/.aws/amazonq` is not a transcript store. Json loads only when it has `history`, `messages`, or `conversation`.

## DeepSeek dsh

Load is unmeasured. Resume is `UNMEASURED`.

The home is `DSH_HOME` or `%USERPROFILE%\.dsh\**\session.v3.jsonl.zstd`. The header is the parent directory name. The file is counted from its size and is not opened. There is no title field. The body is `session.v3.jsonl.zstd`, and it is not decompressed. It is counted, not loaded. The walk skips `node_modules` and `.git` and does not treat dependency trees as sessions.

## Factory

Load is absent. Resume is `UNMEASURED`.

The home is empty and the count stays null. No session directory is documented, and the walker has no Factory enumerator. `droid --resume` is documented and not wired.

## Windsurf

Load is absent. Resume is `UNMEASURED`.

The home is empty and the count stays null. No transcript path is documented. Windsurf in the editor-host list is only a place where Cline, Kilo, or Roo tasks can live.

## Augment

Load is absent. Resume is `UNMEASURED`.

The home is empty and the count stays null. No transcript path is documented, and the walker has no Augment enumerator.

## Claude Code sessions folder

Load is unmeasured. Resume is `UNMEASURED`.

The home named here is `%APPDATA%\Claude\claude-code-sessions`. There is no title, header, or body. It is not in the default places. The program does not walk it. It is distinct from Claude Code projects and from local-agent-mode sessions.

## Claude.ai IndexedDB

Load is unmeasured. Resume is `UNMEASURED`.

The home named here is `%APPDATA%\Claude\IndexedDB\https_claude.ai_0.indexeddb.leveldb`. The body would be IndexedDB leveldb, not a jsonl reader. The program does not open this store. It is not a Claude Code or Claude Desktop jsonl session.

## agy

Load is unmeasured. Resume is `UNMEASURED`.

No home is written, no transcript path is written, and no title field is written. This is not Gemini CLI `~/.gemini/tmp`. The program does not walk it.

## antigravity

Load is unmeasured. Resume is `UNMEASURED`.

The home named here is `%USERPROFILE%\.gemini\antigravity`. No title field is written. This is not Gemini CLI `~/.gemini/tmp`. The program does not walk it.

## antigravity-ide

Load is unmeasured. Resume is `UNMEASURED`.

The home named here is `%USERPROFILE%\.gemini\antigravity-ide`. No title field is written. This is not Gemini CLI `~/.gemini/tmp`. The program does not walk it.

## antigravity-cli

Load is unmeasured. Resume is `UNMEASURED`.

The home named here is `%USERPROFILE%\.gemini\antigravity-cli`. No title field is written. This is not Gemini CLI `~/.gemini/tmp`. The program does not walk it.

## cosmos

Load is unmeasured. Resume is `POINTER`.

The home named here is `V:\a\ai\COSMOS\live\state\SEED.json`. The header schema is `cosmos-session-seed/1`. This is a pointer only, not a transcript and not a working folder. The seed check verifies `SEED.decl.json` length and sha. It does not list turns.

## cosmos-code

Load is unmeasured. Resume is `POINTER`.

There is no title and no separate home. The header is an attempt-local `session.jsonl`. The body would be jsonl events whose required field is `ev`. This is not a transcript home and it is not parsed as one. The program does not walk it. Door and model are on the first session start line.
