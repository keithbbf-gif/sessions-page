# Integration

One engine, three shells. Do not fork the session code.

1. Standalone app first. The product is the native desk window, `CM Sessions.exe`. It finds, reads, and resumes local sessions with no Cosmos, no cDeck, and no browser. It does not bind a port.
2. Integral to COSMOS. When Cosmos is installed, the same engine is called in-process. Cosmos is the body. cmSessions is not the body.
3. A plugin for Cosmos Code. Cosmos Code is a launch target and a host. The hook is `cosmos_code_hook.py`. It does not copy the engine into the Cosmos Code tree.

COSMOS already loads this engine. Do not edit `cosmos_service.py`, `app.js`, or `header.js`.

The adapter is `V:\a\ai\COSMOS\cosmos\cosmos_session_tools_kit.py`. `ENGINE` in that file is `builds/sessions-page/engine.py`, which on this machine is `V:\a\ai\COSMOS\builds\sessions-page\engine.py`.

COSMOS already calls the engine through `cosmos_session_tools_kit.py` with port null. `window` is `desk`. The kit does not open a second port, and it does not write `live\`.

`GET /api/v1/session_tools` already calls `snapshot` on the kit. `POST /api/v1/session_tools` already calls `run`. A presence check lists verbs and whether the usual folders exist. It does not walk transcripts, and it does not create a session directory.

The in-process call from the sessions folder is `plugin_api.py`. `snapshot` reads presence. `call` runs one verb through the kit when that kit can be loaded, and otherwise through the engine. `formats` reads the format index. It does not walk a store to do that. The plug does not bind a socket.

The same facts are written for a reader in [consumer/cosmos.md](consumer/cosmos.md).

## The next COSMOS step

The next step is a button that calls `kit.run`. That button is not in this build, and it was not added to cDeck. It does not open a second port, and it does not write `live\`.

## Cosmos Code

`E:\Cosmos_code_repo` is a pile of dated snapshots, not the running package. Do not copy the engine into `E:\Cosmos_code_repo`.

The snapshot descriptor in `E:\Cosmos_code_repo\2026-09-30_v2_product_engine\product_cosmos_code\plugins.py` now has the entrypoint `V:\a\ai\COSMOS\builds\sessions-page\cosmos_code_hook.py:descriptor`. The builtin named `sessions` stays registered. `via` is in-process. `port` is null. `window` is `desk`. `writes_live` stays false. The verbs are find, load, resume, and formats. Scope stays `core/sessions`. The hook does not open a port, it does not start a process, and it does not write `live\`.

`V:\a\ai\COSMOS\cosmos_code` still has no `plugins.py`, so the running Cosmos Code package does not load this descriptor until that snapshot is the package.

The deck script `plugin/deck_sessions_page.js` is only the old page. It still talks to `127.0.0.1:8786` when someone started `serve`. The installed app is the desk window and does not need that port.
