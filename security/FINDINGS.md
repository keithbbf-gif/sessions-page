# Findings

## BIND

Reviewed `V:\A\Ai\sessions-page-teams\security\sessions_page.py` only. No product code was edited. The server was not started.

### serve binds 127.0.0.1 only

Yes. The only listen address in this file is the literal `("127.0.0.1", port)`.

- Lines 221–225: `Bound` subclasses `ThreadingHTTPServer` and sets only `daemon_threads`. The listen is `httpd = Bound(("127.0.0.1", port), Handler)`. This subclass does not set `address_family` or replace `server_address`.
- Lines 308–310: the `serve` command takes `--port` (default 8786) and `--no-browser`. It has no host argument.
- Lines 344–345: `serve` calls `_serve(args.port, ...)`. The port is the only address input.
- Lines 226–228: if that listen fails, the process emits `BIND_FAILED` for that port and returns 2. It does not try another interface.
- Line 246: the ready URL is `http://127.0.0.1:{port}/`, the same address passed to the constructor.
- Line 248: `httpd.serve_forever()` is what stays on that socket.

`_ours` (lines 64–71) and `_open_page` (lines 74–89) open `http://127.0.0.1:{port}/` as clients. They do not listen.

### frozen no-args binds a port

Yes. A frozen executable with no arguments takes the listener path. It does not call the desk.

- Lines 269–271: `main()` returns `_launch_gui()` when `argv` is `None`, `sys.frozen` is true, and `len(sys.argv) <= 1`. It does not parse a subcommand.
- Lines 256–266: `_launch_gui` walks 8786 through 8795 (`range(preferred, preferred + 10)`, preferred default 8786). If `_ours(port)` is already true, it only opens that page and returns 0, so that pass does not bind. Otherwise it calls `_serve(port, open_browser=True)`, which is the listen above. The first port in that range that listens successfully stays bound. If all ten fail, line 265 reports that and returns 2.
- Lines 346–348: `desk.main()` runs only for the `desk` subcommand. Frozen no-args never reaches it.
- Lines 14–16: the docstring says the frozen no-args exe opens the full-screen UI. That path is `_launch_gui` plus `_open_page` (lines 74–89), after the loopback listen, not `desk.py`.

Unfrozen `main()` does not take this branch. Line 270 requires `sys.frozen`.

### Docs in this tree that disagree

These say a no-args or packaged start opens the desk and does not bind. That is not what lines 270–271 do.

- `HANDOFF.md` line 26
- `SUMMARY.md` lines 9–17
- `docs/integration.md` line 5
- `docs/consumer/safety.md` line 5
- `docs/consumer/README.md` lines 17 and 33–39
- `docs/consumer/install.md` lines 17–29

`README.md` lines 26 and 34 match the code: `serve` is loopback, and a double-click opens `http://127.0.0.1:8786/`. `desk.main` (`desk.py` lines 2021–2022) says it does not bind a socket. That entry is the `desk` command, not frozen no-args.

## LEGAL

Reviewed `V:\A\Ai\sessions-page-teams\security\engine.py` only. No legal file was opened. `engine.py` was not edited.

The gate is `is_legal` at lines 149–154. `_blob` (lines 145–146) lowercases and turns `/` into `\`. A hit is legal when `stream` is exactly `legal`, or when path, cwd, or title contains `\legal\`, `\legal`, `p:\legal`, `v:\ai\legal`, or `\abraxas\`. `p:\legal` and `v:\ai\legal` are already covered by `\legal`, including when the path ends there and has no trailing separator. `\abraxas\` is not: a path or cwd that ends at `abraxas`, with no separator after it, does not match. The word legal in a title does not match unless one of those substrings is present. A relative path that starts at `legal` and never contains `\legal` does not match.

`_hit` (lines 736–753) applies that check. On a match it stores `legal: true` and blanks cwd and title. It still stores `path` (line 745). Claude listing does not open the transcript: `_consume_claude_dir` (lines 981–1007) decides from the folder name via `_claude_project_cwd` (lines 973–978). If that decode does not match, the decoded cwd is dropped (line 1005) and the jsonl path under the projects tree is what gets checked.

### When the gate already matches, a full body is not returned

`_open_hit` (lines 2703–2712) raises `LEGAL_OMITTED` before any full read when `hit["legal"]` is set. If it is not set, it sniffs only the first `HEAD_BYTES` (8192, line 32) and only for `.jsonl`, `.json`, `.md`, and `.txt`, then raises if that header cwd or title matches. These callers go through `_open_hit` before the transcript read: `preview` (line 3438), `import_session` (line 3490), `export_md` (line 3506), `load_record` (line 3121), `anonymize` (line 3981), `strip` (line 4005), and `resume` (line 3868). `dispatch` load (lines 4302–4303) uses `load_record`. `recover` (lines 3711–3718) refuses a matching path, and a jsonl whose header matches, before `_jsonl_state` reads the file (line 3629).

`build_index` (lines 3540–3542) writes a blank cwd and title for a legal row. It still writes `path` (line 3539). The index does not contain transcript text for a row the gate marked legal.

Some listers open bytes before `_hit` blanks the row. That text is not copied onto the hit when the gate then matches, but the file was opened:

- Continue, Amp, and OpenHands: `_json_obj` (lines 1716–1720) reads up to 256KB of the session file, then `_hit` (`_enum_continue` line 1774, `_enum_amp` line 1839, `_enum_openhands` line 1867).
- Cursor agent jsonl: `_claude_meta` (lines 903–923) reads the header, including a user line in that window, before `_hit` (lines 1240–1242).
- Codex, loose jsonl, and goose jsonl: `_sniff` reads 1024 bytes before `_hit` (lines 1038, 1410, 1808).
- Grok reads `summary.json` whole (line 957) before `_hit`. It does not open `chat_history.jsonl` there.
- Claude project jsonl is not opened at list time (lines 981–1007). Dsh counts `session.v3.jsonl.zstd` and does not decompress (lines 1966 and 1981–1984).

### Bodies can still be read

Yes, in these cases.

1. Abraxas with no trailing separator. The only abraxas mark is `\abraxas\` (line 153). `\legal` does not have this hole, so `p:\legal` and `v:\ai\legal` still match. A cwd or path that ends at `abraxas` stays `legal: false`. Claude folder decode that ends there is not flagged, and line 1005 then stores a blank cwd, so the projects-tree jsonl is unmarked too. `_enrich` (lines 2231–2251) opens that jsonl. `_first_user_title` (lines 846–868) reads up to 256KB and can keep the first user line, cut to 80 characters, as the title. `_open_hit` does not refuse. `preview`, `load_record`, import, and export then read the body, up to `MAX_BYTES` (48MB, line 29) in `_read_jsonl` (lines 2470–2478).

2. The second check is a short header only. `_open_hit` (lines 2708–2711) does not sniff `.db`, `.sqlite`, `.vscdb`, `.jsonl.zst`, `.zstd`, or `.html`, and it does not see a mark past the first 8192 bytes. Database enumerators set the flag from path, cwd, title, or stream columns, not from message text (`_enum_openwork` lines 1388–1394, `_enum_hermes` lines 1511–1514, `_antigravity_files` lines 2065–2068). If that flag is false, `load_record` (lines 3143–3172) and the preview helpers read the body. `_read_jsonl_zst` (lines 2450–2467) decompresses a missed `.jsonl.zst` the same way.

3. Find's legal bit is not the bit preview reloads. `_live_load` (lines 2307–2313) stores the walk hit before `_enrich`. `_by_id` (lines 2397–2400) returns that walk hit. `_enrich` can set `legal` from a title taken from the first user line after reading up to 256KB (lines 2243–2251). `_open_hit` does not use that user-line title. A row find just marked legal can still be opened by preview, load, import, and export when the walk hit was not already legal and the header regex does not see a mark. The same split applies when the caller does not use the live cache: `_by_id` walks again with no enrich (lines 2401–2406).

4. `diff_files` (lines 4144–4147) and `check` (lines 4165–4209) never call `is_legal`. Diff reads both files whole. Its result is hashes and a turn delta, not the transcript text. `check` for `sit` (lines 4206–4209) reads the file as text and does not return that text. `recover` does call the gate.

5. A body that gets past the gate is labeled non-legal on the way out. `load_record` sets `"legal": False` on the transcript head (line 3185) after `_open_hit` returns. That does not by itself open a file the gate already refused.

## PATH

Reviewed export, import, and load in `V:\A\Ai\sessions-page-teams\security\engine.py` only. `engine.py` was not edited. No product process was started.

Yes. A user-supplied path can leave the session file. Load, import, and export all resolve the id through `_by_id`, then read `hit["path"]`.

- Lines 2410–2414: after the home walk misses, `_by_id` treats the caller `id` as a filesystem path and accepts it when `Path(want).is_file()` is true. `is_file` follows links. `_is_real_file` (lines 224–228) is not used.
- Lines 2418–2429: `_hit_from_file` returns that path for a `chat_history.jsonl` beside `summary.json`, a uuid `.jsonl`, or a rollout-shaped name. It does not require the resolved file to sit under a session home.
- Lines 4302–4303: `dispatch` load calls `_by_id` and then `load_record`. Lines 3488–3493: `import_session` does the same, then writes the copy. Lines 3504–3509: `export_md` does the same, then writes Markdown.
- Line 3122: `load_record` opens `Path(hit["path"])` with no home check. Lines 3149–3166 read the jsonl, a sibling `.zst`, or the json. Those reads follow a link.

Two paths stored on the session record take the same read, still with no root check:

- Lines 1338–1344: a cowork catalog `filename` is joined as `base / filename` and kept when `is_file()` is true. An absolute filename replaces `base`. A filename that climbs out of `ordered_transcripts` is kept. `load_record` then reads that path for cowork (lines 3132–3134).
- Lines 1185 and 1117–1135: a codex `rollout_path` is kept whenever that file exists. It is not limited to the session tree. Load, import, and export then read it.

The copy name does not add a second escape. `legal_id` (lines 51 and 140–142) strips `\/:*?"<>|` from the stem. Import writes `out_dir / "{id}.ctr.jsonl"` (lines 3207–3210 and 3496). Export writes `out_dir / "{id}.md"` (line 3518). `out` itself is the caller-chosen directory (lines 4309 and 4318), which the load and export docs already allow.

Fix: resolve the candidate with `_is_real_file`, and reject it unless `path.resolve()` is under the session home; do not accept a raw `id` path outside that home, and apply the same check to cowork `filename` and codex `rollout_path` before `load_record` reads them.

## XSS

Reviewed `ui/index.html`, `ui/app.js`, and the desk (`desk.py` plus the ledger text it fills). Session title, project (last `cwd` segment or stream), drive path and volume label, and transcript fields are treated as HTML. No payloads below.

`desk.py` has no XSS sink. Preview and status text go through Tk `insert` / `configure(text=)` (`desk.py` 1189, 1197, 1209, 1216; `ledger_master.py` 866, 1457), which does not parse markup.

- `ui/index.html:999` — `escapeJs` only backslash-escapes quotes and is then placed inside a double-quoted `onclick` (`1601`, `1605`, `1653`, `1900`). A backslash does not protect an HTML attribute, and `&` is not encoded, so an id can still break the attribute. Fix: stop embedding ids in handlers; set a `data-id` and bind the click in script.
- `ui/index.html:1741` — project names from `mapHitToSession` (`1104`) are concatenated into `onclick` and into element text (`1743`, `1755`, `1763`, `1769`, `1780`) with no encoding. Fix: `escapeHtml` the visible name and pass the project via a data attribute, not an inline string.
- `ui/index.html:1853` — drive id, name (includes the volume label), kind, path, and note are written into HTML and into `onclick` / `ondblclick` (`1856`, `1871`, `1872`, `1882`, `1884`); the path helper only doubles backslashes. Fix: `escapeHtml` every visible field and open the folder from a data attribute.
- `ui/index.html:2700` — calendar title, summary, project, model, cost, and event text copied in `syncCalendarFromSessions` (`1269`, `1283`) are inserted raw (`2728`, `2732`, `2753`, `2789`, `2902`, `3039`, `3042`, `3051`, `3072`), including into `title` attributes. Fix: `escapeHtml` each of those fields before building the calendar HTML.
- `ui/index.html:1987` — transcript body is escaped, but `roleTitle` (built from `t.name` and `s.model` at `1969` and `1973`) and `t.seq` are not. Fix: `escapeHtml` the role label and the sequence the same way as the body.
- `ui/index.html:2192` — `inlineEditSessionTitle` puts the current title and the id into `outerHTML` (`value` and an inline handler) with no encoding. Fix: set `input.value` and listen for blur in script; do not build the input from the title.
- `ui/index.html:2247` — `openTriggerModal` writes `anchorName` straight into `value="..."`. Fix: `escapeHtml(anchorName)` before interpolation (or set the input’s `.value` after creating the node).
- `ui/app.js:775` — `paintCards` assigns `innerHTML` that includes `projectLabel(key)` (the cwd’s last segment). Fix: build the card with `textContent`, or escape that label before `innerHTML`.
- `ui/index.html:6` — the page loads a remote script with no integrity check and no Content-Security-Policy, and the rest of the file uses inline handlers. Fix: self-host that script (or pin it with SRI) and add a CSP that does not allow unexpected script once the inline handlers are gone.

`ui/app.js` otherwise sets text with `textContent`. The `innerHTML` at `843` and `859` is only a date from `Date`, not session data.

## SECRETS

Searched this worktree for hardcoded tokens, private keys, and logging of environment values. No secret value is copied here.

No private-key block was found. No statement logs an environment value. Path lookups read environment variables and do not print them. name_model.py:97 reads XAI_API_KEY into a request header and does not print it. test_store_fixes.py:417 copies that variable so the test can restore it and does not print it.

- test_csm_core.py:185 — Token-shaped literal in a test payload. Generate it in the test and do not commit the literal.
- test_csm_core.py:189 — Credential-shaped bearer literal. Generate a non-secret placeholder in the test.
- test_csm_core.py:217 — Two token-shaped literals. Generate them in the test and do not commit them.
- test_sessions_page.py:416 — Token-shaped literal written into a fixture. Generate it in the test.
- test_sessions_page.py:421 — Same literal repeated in an assertion. Compare against the test-local value.
- test_sessions_page.py:422 — Same literal repeated again. Compare against the test-local value.
- test_scale_and_clusters.py:265 — Hardcoded session key. Generate the key in the test or read it from the environment.

`csm_core/redact.py` masks token-shaped strings. It does not log the original value. It is not wired into `engine.redact` in this change.
