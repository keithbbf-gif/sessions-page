# Sessions inside COSMOS

You do not start a port for Sessions inside COSMOS. The window is the desk. COSMOS calls the same engine in-process. `port` is null. `window` is `desk`.

The engine COSMOS loads is `V:\a\ai\COSMOS\builds\sessions-page`. The adapter is `V:\a\ai\COSMOS\cosmos\cosmos_session_tools_kit.py`. COSMOS already routes its session tools through that file. You do not edit `cosmos_service.py` to use it, and this program does not change the COSMOS ledger.

A presence check lists the verbs and whether the usual folders exist. It reports `port` null and `window` desk. It does not walk transcripts, and it does not create a session directory. A count stays empty until something actually runs Find. Legal rows are still omitted from any read. Crash recovery inside COSMOS is the same rule as the command: a sibling `.bak` is copied only when apply is really on, and the broken bytes are not rewritten in place.

You do not run `serve` to make COSMOS work. `serve` is only the old loopback page. Inside COSMOS there is no second Sessions port.

The in-process plug is `plugin_api.py` in the sessions folder. It does not bind a socket, and it does not start `OpenWork.exe` or `grok.exe`. A presence check through the plug stamps the same two facts: `port` null and `window` desk. Asking it to run a verb uses the COSMOS adapter when that adapter can be loaded, and otherwise the engine directly. Asking it for formats reads the format index. It does not walk a store to do that.

## Cosmos Code

Cosmos Code uses an in-process hook, not a second ledger. The hook is `cosmos_code_hook.py` in the sessions folder. It does not open a port, it does not start a process, and it does not write `live\`.

The hook names the sessions plug. It stays in-process on the desk. `port` is null. `window` is `desk`. The verbs it names are find, load, resume, and formats. Opening the plug returns the same presence check as `plugin_api.py`. There is no second session list and no second copy of the program to start.
