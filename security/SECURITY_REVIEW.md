# Security review

Defensive review only. No product behavior was changed except adding `csm_core/redact.py`, which masks token-shaped strings and does not log the original. Nothing here is a runtime observation: the server was not started, and no frozen executable was launched. Line-level notes are in `FINDINGS.md`. No payloads and no secret values are included.

## Bind

The only listen address in `sessions_page.py` is loopback. `serve` constructs the server with `("127.0.0.1", port)`, accepts `--port` (default 8786) and `--no-browser`, and has no host argument. If that listen fails, the process reports `BIND_FAILED` and exits 2. It does not try another interface. The ready URL is `http://127.0.0.1:{port}/`.

A frozen executable with no arguments does bind. `main()` calls the GUI launch path when the process is frozen and there is no subcommand. That path tries ports 8786 through 8795, listens on the first success, and opens the browser. It does not call `desk.main`. Unfrozen `main()` does not take this path. The `desk` command is a separate entry and does not bind.

`README.md`, `SUMMARY.md`, `HANDOFF.md`, `docs/integration.md`, `docs/consumer/safety.md`, and `docs/consumer/install.md` describe the frozen no-args path as the loopback sheet on `127.0.0.1` ports 8786–8795. They do not say that start is the zero-port desk. `desk` is the separate command and does not bind. `FINDINGS.md` still cites an older `sessions_page.py`: `_launch_gui` is not lines 256–266, and frozen `main` is not lines 269–271. In this tree `_launch_gui` is lines 585–595, the frozen branch in `main` is lines 598–600, the listen is line 554 (`Bound(("127.0.0.1", port), Handler)`), `serve` is lines 682–683, and `desk.main()` is line 686.

## Legal

`engine.is_legal` counts a legal session and is meant to keep its text closed. Callers that go through `_open_hit` refuse a row the gate already marked. The index stores a blank title and folder for those rows and still stores the path.

The gate is not complete. A mark past a short header, some database and compressed suffixes, and an abraxas path with no trailing separator can stay unmarked. Find's legal bit is not always the bit a later preview or load rechecks. `diff_files` and `check` do not call the gate. Details and the missed cases are in `FINDINGS.md`. No legal file was opened for this review.

## Path

Load, import, and export resolve an id through `_by_id` and then read `hit["path"]`. After the home walk misses, an id that names an existing file is accepted, including through a link, with no requirement that the resolved path sit under a session home. A cowork catalog filename and a codex rollout path can name a file outside that tree and are read the same way. Output stems are sanitized. The fix is to require a non-link resolve under the session home before those reads, and not to accept a raw id path outside that home.

## XSS

The desk writes preview and status text through Tk `insert` and `configure(text=)`, which does not parse markup. The full-screen page treats session title, project, drive path, volume label, and some transcript fields as HTML. Several builders concatenate those fields into `innerHTML` or inline `onclick` handlers. `escapeJs` does not make an HTML attribute safe. Fixes are to encode visible text and to pass ids through data attributes instead of inline handlers. The page also loads a remote script with no integrity check and has no Content-Security-Policy. No payloads are listed in `FINDINGS.md`.

## Secrets

The worktree search found no private-key block and no log of an environment value. `XAI_API_KEY` is read into a request header and is not printed. Several tests still contain token-shaped literals; those literals are not copied into this review. They should be generated inside the test. `csm_core/redact.py` is a local mask for token-shaped strings. It returns the masked text only.

## Loopback token, rate limit, and HTTP errors

The source, not a running server, shows three controls on the loopback page.

Each boot of `_serve` draws a nonce with `secrets.token_hex(24)` and injects `<meta name="cm-token">` into HTML (`_inject_token`). Mutating browser POSTs must send that value as `X-CM-Token`. The check is `_mutation_allowed` / `_token_mutation`: `POST /api/shutdown`, and on `POST /api/run` the actions `handoff`, `strip`, and `open_folder`, plus `resume` when `launch` is true and `recover` or `crash-recover` when `apply` is true. A token that does not match is 403. `Origin` or `Referer` without a match is 403. `CMSESSIONS_REQUIRE_TOKEN=1` requires a match on those actions even with no origin. This is a per-boot CSRF check for this page. It is not a user login.

`_allow_rate` limits `POST` by client address. Mutating actions (`_rate_mutation`, plus shutdown) use `CMSESSIONS_MUTATE_RATE` when set (`N` or `N/seconds`), otherwise 20 per 10 seconds (`_mutate_budget`). Other `POST /api/run` bodies use 240 per 60 seconds. Over the limit is 429 `RATE_LIMIT`.

`Handler.do_GET` and `Handler.do_POST` map failures through `csm_core.error_handlers.to_http` (`_page_error_body`, `_internal_body`). The JSON `message` and `detail` are the public sentence. The exception class name, traceback, and path are not copied. An unknown exception is 500 `code` `internal`, message `Something went wrong.`

## Residual risk

The listener is local-only in source and still reachable by other principals on the same machine while it stays bound. The per-boot token does not stop another local process that can read the page HTML. The socket, the port chosen inside 8786–8795, and failure behavior were not executed.

Owned docs in this tree describe the frozen no-args listener. `plugin/deck_sessions_page.js` still says the installed app is the desk window (the `HOST` note under `mount`). The legal gate can miss a body. Path checks can open a file outside the session home. The full-screen page can treat session fields as HTML. Test fixtures can still hold token-shaped literals. This commit does not change those behaviors.

## What was not reviewed

- Runtime behavior and a second local client. The token, rate limit, and `to_http` notes above are from reading `sessions_page.py` and `csm_core/error_handlers.py`. The server was not started.
- Installers, packaging, dependency versions, and hosts or ports outside `sessions_page.py`.
- Wiring `csm_core.redact` into `engine.redact` or replacing the test literals. Those files were left unchanged.
