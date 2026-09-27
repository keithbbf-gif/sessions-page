# One registration, later

The sessions tools run without Cosmos. Core already calls
`cosmos_session_tools_kit` from `GET/POST /api/v1/session_tools`. That file is
the adapter. It does not change `cosmos_service.py`.

When the cDeck UI pass is closed, add one script. Do not edit `app.js` or `header.js`.

```html
<script src="deck_sessions_page.js"></script>
```

Optional mount, new id only:

```html
<section id="panel-sessions-page"></section>
```

Start the program first:

```
py -3.14 builds/sessions-page/sessions_page.py serve --port 8786
```

The script paints only `#panel-sessions-page`. If that node is absent, it does nothing.
