# Security review

Defensive review only. No product behavior was changed except adding `csm_core/redact.py`, which masks token-shaped strings and does not log the original. Nothing here is a runtime observation: the server was not started, and no frozen executable was launched. Line-level notes are in `FINDINGS.md`. No payloads and no secret values are included.

## Bind

The only listen address in `sessions_page.py` is loopback. `serve` constructs the server with `("127.0.0.1", port)`, accepts `--port` (default 8786) and `--no-browser`, and has no host argument. If that listen fails, the process reports `BIND_FAILED` and exits 2. It does not try another interface. The ready URL is `http://127.0.0.1:{port}/`.

A frozen executable with no arguments does bind. `main()` calls the GUI launch path when the process is frozen and there is no subcommand. That path tries ports 8786 through 8795, listens on the first success, and opens the browser. It does not call `desk.main`. Unfrozen `main()` does not take this path. The `desk` command is a separate entry and does not bind.

`HANDOFF.md`, `SUMMARY.md`, `docs/integration.md`, and `docs/consumer/safety.md`, `README.md`, and `install.md` say a packaged or no-args start opens the desk and does not bind. That does not match the frozen no-args path. Root `README.md` matches the code.

## Legal

`engine.is_legal` counts a legal session and is meant to keep its text closed. Callers that go through `_open_hit` refuse a row the gate already marked. The index stores a blank title and folder for those rows and still stores the path.

The gate is not complete. A mark past a short header, some database and compressed suffixes, and an abraxas path with no trailing separator can stay unmarked. Find's legal bit is not always the bit a later preview or load rechecks. `diff_files` and `check` do not call the gate. Details and the missed cases are in `FINDINGS.md`. No legal file was opened for this review.

## Path

Load, import, and export resolve an id through `_by_id` and then read `hit["path"]`. After the home walk misses, an id that names an existing file is accepted, including through a link, with no requirement that the resolved path sit under a session home. A cowork catalog filename and a codex rollout path can name a file outside that tree and are read the same way. Output stems are sanitized. The fix is to require a non-link resolve under the session home before those reads, and not to accept a raw id path outside that home.

## XSS

The desk writes preview and status text through Tk `insert` and `configure(text=)`, which does not parse markup. The full-screen page treats session title, project, drive path, volume label, and some transcript fields as HTML. Several builders concatenate those fields into `innerHTML` or inline `onclick` handlers. `escapeJs` does not make an HTML attribute safe. Fixes are to encode visible text and to pass ids through data attributes instead of inline handlers. The page also loads a remote script with no integrity check and has no Content-Security-Policy. No payloads are listed in `FINDINGS.md`.

## Secrets

The worktree search found no private-key block and no log of an environment value. `XAI_API_KEY` is read into a request header and is not printed. Several tests still contain token-shaped literals; those literals are not copied into this review. They should be generated inside the test. `csm_core/redact.py` is a local mask for token-shaped strings. It returns the masked text only.

## Residual risk

The listener is local-only in source and still reachable by other principals on the same machine while it stays bound. The socket, the port chosen inside 8786–8795, and failure behavior were not executed.

Docs that deny a packaged listener are wrong for frozen no-args. The legal gate can miss a body. Path checks can open a file outside the session home. The full-screen page can treat session fields as HTML. Test fixtures can still hold token-shaped literals. This commit does not change those behaviors.

## What was not reviewed

- Runtime behavior, a second local client, and authentication on the loopback page.
- Installers, packaging, dependency versions, and hosts or ports outside `sessions_page.py`.
- Wiring `csm_core.redact` into `engine.redact` or replacing the test literals. Those files were left unchanged.
