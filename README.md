# Sessions page

This directory is its own repository. COSMOS checks it out at `builds/sessions-page`.

From this repository root:

```
py -3.14 sessions_page.py find
py -3.14 test_sessions_page.py
```

Standalone tools for local harness sessions: find, import, export, index, recover, resume.

Harnesses: Grok, Claude Code, Codex, Cursor, Cowork catalog, OpenWork `opencode.db`, Claude Desktop, Gemini (`~/.gemini/tmp/*/chats/*.{json,jsonl}`, or `GEMINI_CLI_HOME` / `GEMINI_SESSIONS`), Hermes (`~/.hermes/state.db` via `HERMES_HOME`, plus `%LOCALAPPDATA%\\hermes\\state.db` and `profiles/*/state.db`), Cline (editor `tasks/*/api_conversation_history.json` and `~/.cline/data/sessions/*/*.messages.json`), Kilo Code (`kilocode.kilo-code` tasks and `~/.kilocode/cli/global/tasks`), Roo Code (`rooveterinaryinc.roo-cline` tasks and `~/.roo/tasks`), Pi (`~/.pi/agent/sessions`, `PI_CODING_AGENT_SESSION_DIR`), GitHub Copilot CLI (`~/.copilot/session-state/*/events.jsonl`), Continue (`~/.continue/sessions/*.json`, skipping `sessions.json`, `CONTINUE_GLOBAL_DIR`), Aider (only `AIDER_CHAT_HISTORY_FILE`), Goose (`sessions.db`, legacy `*.jsonl` only when the db is absent), Qwen (`~/.qwen/projects/*/chats/*.jsonl`), Amp (`~/.local/share/amp/threads/*.json`, `AMP_THREADS_DIR`), OpenHands (`base_state.json`), Crush (`~/.local/share/crush/projects.json`, then each project's `crush.db`), and DeepSeek `dsh` (`~/.dsh/**/session.v3.jsonl.zstd`, counted, not decompressed). Amazon Q stays uncounted unless `AMAZONQ_HISTORY` points at an export. Factory, Windsurf, and Augment have no documented transcript path, so they stay `n: null`. A missing store is `n: null`, not zero. Import of sqlite and zstd stores stays `UNMEASURED`. Legal sessions are counted and their text is not opened. `migrate` and `rebind` stay `DO_NOT_REINGEST`.

```
py -3.14 builds/sessions-page/sessions_page.py find
py -3.14 builds/sessions-page/sessions_page.py import --id <id> --out <dir>
py -3.14 builds/sessions-page/sessions_page.py export --id <id> --out <dir>
py -3.14 builds/sessions-page/sessions_page.py index
py -3.14 builds/sessions-page/sessions_page.py recover --target <file> [--bak <file>] [--apply]
py -3.14 builds/sessions-page/sessions_page.py resume --id <id> [--launch]
py -3.14 builds/sessions-page/sessions_page.py serve --port 8786
```

`serve` is loopback only. Open `http://127.0.0.1:8786/`. The first screen is a Blackline overview: system drives and the default session locations as panes, with a status light. Counts stay unmeasured until a pane is opened. Pick one, then import, export, check recovery, or resume. A full find on this machine is a few seconds. It counts every store and reads headers, not transcript bodies.

Packaged executable (no Python needed to run it):

```
builds\sessions-page\dist\sessions_page.exe
```

Double-click the executable. It opens the Sessions page in the browser at `http://127.0.0.1:8786/` and does not open a console. Quit on the page stops it. Starting it again reopens the page that is already running. The `py -3.14 sessions_page.py …` commands above remain for scripts.

Cursor includes CLI chats, agent transcripts, and read-only composer headers from the desktop state database. Gemini counts chat files under `~/.gemini/tmp`.

Cosmos already routes `GET/POST /api/v1/session_tools` to `cosmos/cosmos_session_tools_kit.py`. That file calls this engine. No edit to `cosmos_service.py`, `app.js`, or `header.js`.

Later UI plug: `plugin/REGISTER.md`.

Recovery checks the file, then copies a verified sibling `.bak` over it after staging the original under `var/stage`. It does not rewrite a corrupt sqlite page in place.

Resume prints the harness command (`grok --resume`, `claude --resume`, `codex resume`, `agent --resume`, `pi --session`, `hermes --resume`, `cline --id` for a `*.messages.json` session, `goose session --resume --session-id`, `qwen --resume`, `copilot --resume=<id>`, `crush --session`). `--launch` starts that command. It does not pass `-p`. OpenWork and Cowork return the session id to focus and do not spawn `OpenWork.exe`. Factory's `droid --resume` flag is documented, and its session directory is not, so those rows are not listed.

Tests: `py -3.14 builds/sessions-page/test_sessions_page.py`
