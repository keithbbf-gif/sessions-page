# Security review

Defensive review only. No product behavior was changed except adding `csm_core/redact.py`, which masks token-shaped strings and does not log the original. Nothing here is a runtime observation: the server was not started, and no frozen executable was launched. Line-level notes are in `FINDINGS.md`. No payloads and no secret values are included.

## Bind

The only listen address in `sessions_page.py` is loopback. `serve` constructs the server with `("127.0.0.1", port)`, accepts `--port` (default 8786) and `--no-browser`, and has no host argument. If that listen fails, the process reports `BIND_FAILED` and exits 2. It does not try another interface. The ready URL is `http://127.0.0.1:{port}/`.

A frozen executable with no arguments does bind. `main()` calls the GUI launch path when the process is frozen and there is no subcommand. That path tries ports 8786 through 8795, listens on the first success, and opens the browser. It does not call `desk.main`. Unfrozen `main()` does not take this path. The `desk` command is a separate entry and does not bind.

`README.md`, `SUMMARY.md`, `HANDOFF.md`, `docs/integration.md`, `docs/consumer/safety.md`, and `docs/consumer/install.md` describe the frozen no-args path as the loopback sheet on `127.0.0.1` ports 8786–8795. They do not say that start is the zero-port desk. `desk` is the separate command and does not bind. `FINDINGS.md` below its resolution note still cites an older `sessions_page.py`: `_launch_gui` is not lines 256–266, and frozen `main` is not lines 269–271. In this tree `_launch_gui` is lines 1032–1042, the frozen branch in `main` is lines 1046–1047, the listen is line 1001 (`httpd = Bound((_SERVE_HOST, port), Handler)`, `_SERVE_HOST` is `"127.0.0.1"` at line 71), `_serve` is lines 742–1029 (the `serve` command calls it at line 1130), and `desk.main()` is line 1133.

## Legal

The resolution note in `FINDINGS.md` records full legal omit as fixed in this tree. The paragraphs below are the older snapshot.

`engine.is_legal` counts a legal session and is meant to keep its text closed. Callers that go through `_open_hit` refuse a row the gate already marked. The index stores a blank title and folder for those rows and still stores the path.

The gate is not complete. A mark past a short header, some database and compressed suffixes, and an abraxas path with no trailing separator can stay unmarked. Find's legal bit is not always the bit a later preview or load rechecks. `diff_files` and `check` do not call the gate. Details and the missed cases are in `FINDINGS.md`. No legal file was opened for this review.

## Path

The resolution note in `FINDINGS.md` records path confinement as fixed in this tree (`_within_homes` before a raw id is read). The paragraphs below are the older snapshot.

Load, import, and export resolve an id through `_by_id` and then read `hit["path"]`. After the home walk misses, an id that names an existing file is accepted, including through a link, with no requirement that the resolved path sit under a session home. A cowork catalog filename and a codex rollout path can name a file outside that tree and are read the same way. Output stems are sanitized. The fix is to require a non-link resolve under the session home before those reads, and not to accept a raw id path outside that home.

## XSS

The desk writes preview and status text through Tk `insert` and `configure(text=)`, which does not parse markup. `ui/index.html` escapes session title, project, drive path, volume label, transcript role (`s.model`, `t.name`, `t.seq`), calendar title, model, project, trigger name, and day summary with `escapeHtml`. Project, drive, calendar, rename, and trigger actions use `data-action` attributes and a delegated click or double-click listener. Ids and paths are not placed in `onclick` JavaScript string literals. The page still loads a remote Tailwind script with no integrity check and has no Content-Security-Policy. No payloads are listed in `FINDINGS.md`.

## Secrets

The worktree search found no private-key block and no log of an environment value. `XAI_API_KEY` is read into a request header and is not printed. Several tests still contain token-shaped literals; those literals are not copied into this review. They should be generated inside the test. `csm_core/redact.py` is a local mask for token-shaped strings. It returns the masked text only.

## Loopback token, rate limit, and HTTP errors

The source, not a running server, shows three controls on the loopback page.

Each boot of `_serve` draws a nonce with `secrets.token_hex(24)` (line 744) and injects `<meta name="cm-token">` into HTML (`_inject_token`). Mutating browser POSTs must send that value as `X-CM-Token`. The check is `_mutation_allowed` (lines 867–876) / `_token_mutation` (lines 579–594): `POST /api/shutdown`, `/v1/*` `POST` writes (`_v1_post`, lines 570–576), and on `POST /api/run` the actions `handoff`, `strip`, `open_folder`, `export`, `import`, `convert`, `index`, and `anonymize`, plus `resume` when `launch` is true and `recover` or `crash-recover` when `apply` is true. A token that does not match is 403. `Origin` or `Referer` without a match is 403. `CMSESSIONS_REQUIRE_TOKEN=1` requires a match on those actions even with no origin. This is a per-boot CSRF check for this page. It is not a user login.

`_handle_solaro_panel` handles `/v1/*` requests (lines 982–984) and `GET /v1/*` stays readable without the boot token, whereas `POST` panel requests require `X-CM-Token` when `Origin`/`Referer` is present (`_v1_post`, lines 570–576). All mutating actions in `_token_mutation` are also covered by `_rate_mutation` (lines 597–613).

`_allow_rate` (lines 878–883) limits `POST` by client address. Mutating actions (`_rate_mutation`, plus shutdown) use `CMSESSIONS_MUTATE_RATE` when set (`N` or `N/seconds`), otherwise 20 per 10 seconds (`_mutate_budget`, lines 549–563). Other `POST /api/run` bodies use 240 per 60 seconds. Over the limit is 429 `RATE_LIMIT`.

`Handler.do_GET` and `Handler.do_POST` map failures through `csm_core.error_handlers.to_http` (`_page_error_body`, `_internal_body`). The JSON `message` and `detail` are the public sentence. The exception class name, traceback, and path are not copied. An unknown exception is 500 `code` `internal`, message `Something went wrong.`

## Residual risk

The listener is local-only in source and still reachable by other principals on the same machine while it stays bound. The per-boot token does not stop another local process that can read the page HTML. The socket, the port chosen inside 8786–8795, and failure behavior were not executed.

Owned docs in this tree describe the frozen no-args listener. `plugin/deck_sessions_page.js` says the packaged app serves the loopback page on ports 8786–8795 and that the cDeck plugin connects to `127.0.0.1:8786` when that page is running. `ui/index.html` escapes project, drive, transcript, calendar, and trigger strings and binds those clicks with `data-action` listeners. The page still loads a remote Tailwind script with no integrity check and has no Content-Security-Policy. Test fixtures can still hold token-shaped literals.

## What was not reviewed

- Runtime behavior and a second local client. The token, rate limit, and `to_http` notes above are from reading `sessions_page.py` and `csm_core/error_handlers.py`. The server was not started.
- Installers, packaging, dependency versions, and hosts or ports outside `sessions_page.py`.
- Wiring `csm_core.redact` into `engine.redact` or replacing the test literals. Those files were left unchanged.
