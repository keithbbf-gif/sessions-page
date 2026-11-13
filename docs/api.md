# API

`sessions_page._serve` binds `127.0.0.1` and handles these routes on the nested `Handler` ([sessions_page.py](../sessions_page.py) `sessions_page._serve`). `Handler._get` serves the three GETs. `Handler.do_POST` serves `POST /api/run` by calling `engine.dispatch`. The path is the request path with any query string removed. `Handler._cors` echoes `Origin` only when it starts with `http://127.0.0.1` or `http://localhost`.

These are not the Cosmos `/api/v1/session_tools` routes. The HTTP handler does not pass a `homes` argument, so `engine.dispatch` keeps `homes=None`.

A failure inside `Handler._get` is 500 `{"error": "INTERNAL", "detail": <exception class name>}`.

## GET /api/verbs

`Handler._get` returns 200 JSON:

```json
{"verbs": ["…"], "harnesses": ["…"]}
```

`verbs` is `list(engine.VERBS)`. `harnesses` is `list(engine.HARNESSES)`. Nothing is added or filtered.

`engine.VERBS`, in order: `find`, `preview`, `import`, `export`, `index`, `recover`, `resume`, `scan`, `load`, `convert`, `diff`, `check`, `anonymize`, `crash-recover`, `strip`, `strip_dry`, `doi`, `formats`, `handoff`.

`engine.HARNESSES`, in order: `grok`, `claude`, `codex`, `cursor`, `cowork`, `openwork`, `claude_desktop`, `gemini`, `hermes`, `cline`, `kilo`, `roo`, `pi`, `copilot`, `continue`, `aider`, `goose`, `qwen`, `amp`, `openhands`, `crush`, `amazonq`, `dsh`, `factory`, `windsurf`, `augment`, `agy`, `antigravity`, `antigravity-ide`, `antigravity-cli`.

`migrate` and `rebind` are not in this list. They are closed actions on `POST /api/run` only.

## GET /api/homes

`Handler._get` returns 200 `{"homes": engine.home_status()}`.

`engine.home_status` calls `engine.default_homes`. It checks presence only. It does not walk transcripts, and `n` stays null.

Each row has:

- `harness`: one name from `engine.HARNESSES`
- `present`: the path exists and is not a symlink
- `path`: the path string when present, otherwise null
- `n`: always null
- `status`: `PRESENT` or `ABSENT`

An `OSError` while checking the path is treated as absent.

## GET /api/places

`Handler._get` returns 200 the dict from `engine.places()`, with no wrapper.

`engine.places` calls `engine.list_drives`, then `engine.home_status` on `engine.default_homes`. Counts stay null until `find`.

```json
{"drives": ["…"], "homes": ["…"]}
```

Each drive row, built by `engine.list_drives` with `engine._volume_fields` or `engine._volume_row_timed`, has `id`, `path`, `label`, `kind`, `fs`, `total`, `free`, and `ready`. `kind` is `unknown`, `noroot`, `removable`, `fixed`, `remote`, `cdrom`, or `ramdisk`. On a non-Windows host the only row is `id` `/`, `path` `/`, `kind` `fixed`, and `ready` is whether `/` exists. A Windows volume that is not `fixed` or `ramdisk` gets a short wait; if it does not answer, the row stays not ready, with an empty label and filesystem and null sizes.

Each home is a `engine.home_status` row plus:

- `candidate`: the default path string, or null when that harness has no default path. This is set even when the folder is absent.
- `drive`: the `X:` letter from `engine._drive_letter` of the present path, or else of `candidate`, or null.

`path` is still only set when the home is present.

## POST /api/run

`Handler.do_POST` reads a JSON object and calls `engine.dispatch(str(body.get("action") or ""), body)`.

Body rules in `Handler.do_POST`:

- A missing `Content-Length` is read as `{}`.
- A `Content-Length` that is not an integer, is negative, or is greater than 1_000_000 is 400 `{"error": "BAD_REQUEST", "detail": "body length"}`, and the connection is closed.
- Invalid JSON is 400 `{"error": "BAD_REQUEST", "detail": <message>}`.
- A JSON value that is not an object is 400 `{"error": "BAD_REQUEST", "detail": "body must be an object"}`.

`engine.dispatch` uses the action string it was given. When that string is empty it reads `body["action"]`, then `body["verb"]`.

Success is 200 and the dict `engine.dispatch` returned. `engine.PageError` is 400 `{"error": <kind>, "detail": <message>}`. Any other exception is 500 `{"error": "INTERNAL", "detail": <exception class name>}`.

An action that is not one of the verbs below, including an empty action, raises `PageError("BAD_ACTION", …)` from `engine.dispatch`.

Most verbs return `engine._result`: `schema` is `engine.SCHEMA` (`cosmos-session-tools-result/1`), plus `verb`, `kind`, `gate`, and `legal_omitted`, plus any extra keys the callee added.

Session verbs other than `find` resolve homes with `engine._homes_for`. A set `body["store"]` becomes `engine._store_homes` for that one store. Otherwise the homes are `engine.default_homes`. `find` does not call `engine._homes_for`, so a `store` field on `find` is ignored.

Where a verb takes `out` and the field is omitted, the directory is `engine.var_dir() / "exports"`. `index` is the exception: it writes `engine.var_dir() / "index.jsonl"`.

Verbs that open one transcript call `engine._open_hit` first. A legal row raises `PageError("LEGAL_OMITTED", …)` and the body is not read. `find` counts legal rows and does not open them.

### Closed actions

These are not in `engine.VERBS`. `engine.dispatch` still handles them.

- `migrate` and `rebind` return `engine._result` with kind `DO_NOT_REINGEST` and gate `detail` `666 re-ingest and rebind stay closed`. No other function runs.

### Verbs

`doi` returns `engine._result("doi", "UNPROVEN", {"detail": "citation existence is not fetched"})`. It does not fetch a citation. No other function runs.

`formats` imports `formats` and returns `engine._result("formats", "OK", formats.catalog())`. `formats.catalog` does not read a home or a transcript. The gate is `{"schema": "cmsessions-format-index/1", "n": <count>, "formats": […]}`. Each format row has `harness`, `prefix`, `title`, `home`, `header`, `title_fields`, `body`, `load`, `resume`, and `notes`. If `formats` cannot be imported, `engine.dispatch` raises `PageError("UNMEASURED", "formats")`.

`preview` calls `engine.preview`. Body: `id` is required, or `PageError("NOT_FOUND", "id is required")`. `turns` defaults to 6 and must be an integer from 1 to 100 (`engine._bounded_int`). `chars` defaults to 400 and must be an integer from 10 to 5000. `store` selects the home. Kind is `OK` or `TRUNCATED`. The gate, from `engine._preview_result`, is `id`, `n_turns`, `shown`, and `turns`. Each shown turn is `seq`, `role`, and `text`. `engine.preview` reads through `engine._preview_openwork`, `engine._preview_hermes`, `engine._preview_antigravity`, `engine._preview_cowork`, or a short jsonl or json read. A cursor `store.db`, or any other unread path, raises `PageError("UNMEASURED", …)`.

`find` calls `engine.find` ([engine.py](../engine.py) `engine.find`, `engine.dispatch`). Body: `query` or `q`, `harness` or `family`, `cwd`, `limit`, `drive`, and `fresh`. `limit` defaults to `engine.DEFAULT_LIMIT` (200) and must be an integer from 1 to 2000. `fresh` must be a boolean when present; the default is false. A non-boolean `fresh` is `PageError("BAD_INPUT", "fresh must be boolean")`. Homes are `engine.default_homes` only. Kind is `OK`. The gate is `n`, `n_shown`, `n_legal`, and `families`. Extra keys are `hits` (the shown rows) and `n`. `legal_omitted` is the legal count. Each hit, from `engine._hit`, has `id`, `harness`, `vendor_id`, `path`, `cwd`, `title`, `stream`, `legal`, `updated`, `bytes`, and `aliases`. `engine._enrich` may fill `title` and `cwd` on the shown rows, and may then mark a row legal and blank those two fields. A legal hit keeps `title` and `cwd` empty. Each family row is `family`, `status`, `path`, `n`, and `n_legal`. `status` is `OK` when that store is listed, `ABSENT` when it is not, or, when `engine._walk_report` skipped a bad store, that store's `PageError` kind or `UNREADABLE`. Absent and failed families have `n` null.

`handoff` requires `id`, or `PageError("NOT_FOUND", "id is required")`. `target` or `harness` is the target harness; the default is `grok`. `out` is the export directory. `store` selects the home. `engine.dispatch` calls `engine.export_md`, then `engine._by_id`, then `engine.record_handoff`. The return value is the export record with `verb` set to `handoff` and `handoff` set to the appended record. `engine.record_handoff` appends one line to `handoffs.jsonl` under `engine.var_dir`. That record has `schema` `cmsessions-handoff/1`, `ts`, `parent`, `parent_harness`, `target`, `binary`, `pid`, `export`, and `cwd`. The child id is not known, so `binary` and `pid` stay empty on this path. The source session is not modified.

`scan` requires `store` or `path`, or `PageError("NO_STORE", "scan needs a store")`. It calls `engine.scan`, which calls `engine._store_homes` and then `engine.find` with `limit` 20. If the store matches no harness, kind is `UNMEASURED` and the gate is `n` null, `path`, and `families` empty. Otherwise kind is `OK` and the gate is `n`, `families` (the find family rows), and `sample_ids` (up to five hit ids). `legal_omitted` and extra `n` come from that find.

`import` requires `id`. `out` or `out_dir` is the directory. It calls `engine.import_session`. Kind is `OK` or `TRUNCATED`. The gate is `id`, `n_turns`, `source_sha`, and `out_sha`. Extra keys are `written` (from `engine.write_pair`: `jsonl`, `decl`, `sha`, `len`, `n_turns`) and `original_untouched` true. The written names are `<id>.ctr.jsonl` and `<id>.ctr.decl.json`.

`load` requires `id`. With no `out` and no `out_dir`, `engine.dispatch` calls `engine._by_id` and `engine.load_record` and returns `engine._result` with verb `load`. Kind is `OK` or `TRUNCATED`. The gate is `id`, `n_turns`, `source_sha`, and `schema` (`engine.TRANSCRIPT`, `cosmos-transcript/1`). Extra `record` is `head` and `n_turns` only. The turn list is not included. With `out` or `out_dir` set, it calls `engine.import_session` and sets `verb` to `load`.

`convert` requires `id`. `out` or `out_dir` is the directory. It calls `engine.import_session` and sets `verb` to `convert`. There is no separate convert function.

`export` requires `id`. `out` is the directory (`out_dir` is not read). It calls `engine.export_md`. Kind is `OK` or `TRUNCATED`. The gate is `id`, `out` (the `<id>.md` path), `out_sha`, `source_sha`, and `n_turns`. Extra `original_untouched` is true.

`index` calls `engine.build_index`. `out`, when set, is the file path; otherwise the file is `engine.var_dir() / "index.jsonl"`. `store` selects the home. Kind is `OK`. The gate is `n`, `n_legal`, `out`, `out_sha`, and `len`. `legal_omitted` is the legal count. `engine.build_index` calls `engine.find` with no row cap and writes one `sessions-page-index/1` JSON line per hit (`engine.INDEX_SCHEMA`). Line fields are `schema`, `id`, `harness`, `vendor_id`, `path`, `cwd`, `title`, `legal`, `updated`, `bytes`, and `aliases`. Legal rows keep `cwd` and `title` empty.

`recover` and `crash-recover` both call `engine.recover`. `target`, or else `path`, or else `store`, is required, or `PageError("NO_STORE", "recover needs a target")`. `bak` is optional. When it is omitted, `engine.recover` uses `engine._bak_candidates` (sibling files whose names start with the target name and contain `.bak`, newest first). `stage` is optional. `apply` must be a boolean when present; the default is false. A non-boolean `apply` is `PageError("BAD_INPUT", "apply must be boolean")`. `engine.recover` does not edit the broken bytes in place. Kind is `BUSY`, `ALREADY_OK`, `NO_BAK`, `DRY_RUN`, or `OK`. The gate always has `target` and, except on `OK`, `detail`. `DRY_RUN` also has `bak` and `bak_sha`. `OK` has `bak_path`, `bak_sha`, `staged_path`, `staged_sha`, and `restored_sha`. For `crash-recover`, `engine.dispatch` sets `verb` to `crash-recover` after `engine.recover` returns. A missing target is `NO_STORE`. A legal target is `LEGAL_OMITTED`. A suffix other than `.jsonl`, `.db`, or `.sqlite` is `UNMEASURED`. A bak that exists but does not check is `BAD_BAK`. A failed replace is `RESTORE_FAILED`.

`resume` requires `id`. It calls `engine.resume` ([engine.py](../engine.py) `engine.resume`, `engine.dispatch`). `launch` is passed through `bool`, so any truthy JSON value launches; it is not required to be a boolean. `store` selects the home. Kind is `OK` (command only), `LAUNCHED` (process started; gate gains `pid`), `BINARY_ABSENT`, `OPENWORK_FOCUS`, or `UNMEASURED`. The gate carries `id`, `harness`, `argv`, and `launched`, and usually `cwd` and `binary`. `openwork` and `cowork` return `OPENWORK_FOCUS` and do not spawn `OpenWork.exe`. A Cline row whose path does not end in `.messages.json`, and any other harness with no binary in `engine.launch_specs` / `engine._binary_for`, returns `UNMEASURED`. A launch whose `cwd` is set and is not a directory raises `PageError("CWD_MISSING", …)`.

`diff` requires `left` and `right`, or `PageError("NOT_FOUND", "diff needs left and right")`. It calls `engine.diff_files`. Both paths must be files, or `PageError("NOT_FOUND", …)`. Kind is `OK`. The gate is `left_sha`, `right_sha`, `n_turns_delta`, and `identical`. `n_turns_delta` is null when either file is not line-oriented JSON.

`check` calls `engine.check`. `what` defaults to `catalog`. `path` or `store` is required, or `PageError("NO_STORE", "check needs a path")`. `chair` or `sit` defaults to `ccr`. Implemented `what` values are `catalog`, `sqlite`, `seed`, and `sit`. Anything else raises `PageError("UNMEASURED", <what>)`. Success kind is `VERIFIED`.

- `catalog` uses `engine._catalog_file`. No catalog is `NO_STORE`. A catalog that is not a JSON list is `UNPARSEABLE`. A named transcript that is missing is `MISSING_PART`. The gate is `n`, `path`, and `what` `catalog`.
- `sqlite` calls `engine._sqlite_ok`. A directory uses `opencode.db` inside it when that file exists. A failed check is `SQLITE_CORRUPT`. The gate is `what` `sqlite`, `integrity_check`, and `path`.
- `seed` reads `SEED.json` and `SEED.decl.json` beside it, or those names when `path` is already the seed file. A missing file is `NO_SEED`. A length or sha mismatch is `BAD_SEED`. The gate is `what` `seed`, `sha`, `len`, `mac_present`, and `mac_ok` (always null; the mac is not checked).
- `sit` requires a file, or `NO_STORE`. `ccr` requires the text to contain `bucm/1`, and `orc` requires `burestart/3`. A mismatch is `SIT_MIXED`. Any other chair is `UNMEASURED`. The gate is `what` `sit`, `sit`, and `schema`.

`anonymize` requires `id`. It calls `engine.anonymize`, which calls `engine.load_record`, `engine.redact`, `engine.encode_transcript`, and `engine.write_pair`. The directory is `engine.var_dir() / "exports"` when neither `out` nor `out_dir` is set. When `out` is set, that path is used, and a set `out_dir` replaces it. `store` selects the home. Kind is `OK` or `TRUNCATED`. The gate is `n_redactions`, `source_sha`, `out_sha`, and `id`. Extra keys are `written` and `original_untouched` true. The written stem is `<id>.anon`. The source file is not modified.

`strip` and `strip_dry` require `id` or `path` (the `path` string is the session id, not a separate file argument). Both call `engine.strip`. `strip_dry` passes `dry=True`; there is no body flag for that. `out` is the directory for `strip`. `store` selects the home. `engine.strip` drops turns whose role is in `engine._TOOL_ROLES` (`tool_call`, `tool_result`, `system`, `thinking`) and strips the tags in `engine._STRIP_TAGS`. Kind is `OK` or `TRUNCATED`. The gate is `id`, `kept`, `dropped_markers`, and `dry`. `strip_dry` does not write. `strip` also sets `out_sha` and returns `written` from `engine.write_pair` with stem `<id>.strip`, plus `original_untouched` true. The source file is not modified.
