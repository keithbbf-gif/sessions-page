# Sessions page

This directory is its own repository. COSMOS checks it out at `builds/sessions-page`.

From this repository root:

```
py -3.14 sessions_page.py find
py -3.14 test_sessions_page.py
```

Standalone tools for local harness sessions: find, import, export, index, recover, resume.

Harnesses: Grok, Claude Code, Codex, Cursor, Cowork catalog, OpenWork `opencode.db`, Claude Desktop jsonl when that folder exists, Gemini only when `GEMINI_SESSIONS` is set. A missing store is `n: null`, not zero. Legal sessions are counted and their text is not opened. `migrate` and `rebind` stay `DO_NOT_REINGEST`.

```
py -3.14 builds/sessions-page/sessions_page.py find
py -3.14 builds/sessions-page/sessions_page.py import --id <id> --out <dir>
py -3.14 builds/sessions-page/sessions_page.py export --id <id> --out <dir>
py -3.14 builds/sessions-page/sessions_page.py index
py -3.14 builds/sessions-page/sessions_page.py recover --target <file> [--bak <file>] [--apply]
py -3.14 builds/sessions-page/sessions_page.py resume --id <id> [--launch]
py -3.14 builds/sessions-page/sessions_page.py serve --port 8786
```

`serve` is loopback only. Open `http://127.0.0.1:8786/`. The page lists recent sessions. Pick one, then import, export, check recovery, or resume. A full find on this machine is a few seconds. It counts every store and reads headers, not transcript bodies.

Packaged executable (no Python needed to run it):

```
builds\sessions-page\dist\sessions_page.exe verbs
builds\sessions-page\dist\sessions_page.exe serve --port 8786
```

Cursor includes CLI chats, agent transcripts, and read-only composer headers from the desktop state database. Gemini stays unmeasured until `GEMINI_SESSIONS` points at a directory.

Cosmos already routes `GET/POST /api/v1/session_tools` to `cosmos/cosmos_session_tools_kit.py`. That file calls this engine. No edit to `cosmos_service.py`, `app.js`, or `header.js`.

Later UI plug: `plugin/REGISTER.md`.

Recovery checks the file, then copies a verified sibling `.bak` over it after staging the original under `var/stage`. It does not rewrite a corrupt sqlite page in place.

Resume prints the harness command (`grok --resume`, `claude --resume`, `codex resume`, `agent --resume`). `--launch` starts that command. It does not pass `-p`. OpenWork and Cowork return the session id to focus and do not spawn `OpenWork.exe`.

Tests: `py -3.14 builds/sessions-page/test_sessions_page.py`
