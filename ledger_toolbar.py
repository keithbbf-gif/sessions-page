"""Ledger sheet toolbar. One row, packed left to right in parent."""

_BG = "#0C0E12"
_FG = "#E8ECF4"
_BTN = "#1E2430"

_GROUPS = (
    ("maker", "Group by maker"),
    ("project", "Group by project"),
    ("topic", "Group by topic"),
    ("flat", "Flat"),
)

# Old desk tools, remapped onto the ledger. Not separate pages.
_MORE = (
    ("Refresh", "_load_all"),
    ("Build index", "_on_index"),
    ("Load", "_on_load"),
    ("Import", "_on_import"),
    ("Export", "_on_export"),
    ("Anonymize", "_on_anonymize"),
    ("Check recovery", "_on_recover"),
    ("Restore", "_on_restore"),
    ("Check strip", "_on_strip_dry"),
    ("Write strip", "_on_strip"),
    ("Name", "_on_name"),
    ("Quit", "_on_quit"),
)


def _call(desk, name: str) -> None:
    if hasattr(desk, name):
        getattr(desk, name)()


def _button(tk, parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=_BTN,
        fg=_FG,
        activebackground=_BTN,
        activeforeground=_FG,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=("Segoe UI", -13),
        padx=8,
        pady=2,
        cursor="hand2",
    )


def build(parent, desk) -> None:
    tk = desk.tk
    parent.configure(bg=_BG)

    tk.Label(
        parent, text="Session type", fg=_FG, bg=_BG, font=("Segoe UI", -13),
    ).pack(side="left", padx=(12, 6), pady=8)

    for mark in ("CLI", "TUI", "Chat"):
        tk.Label(
            parent,
            text=mark,
            fg=_FG,
            bg=_BTN,
            font=("Segoe UI", -12),
            padx=8,
            pady=2,
        ).pack(side="left", padx=2, pady=8)

    def summaries() -> None:
        if hasattr(desk, "_say"):
            desk._say(
                "Create summaries uses the title and project already on the row. A model summary is not part of this pass.",
                "warn",
            )

    _button(tk, parent, "Create summaries", summaries).pack(side="left", padx=(12, 4), pady=8)

    def set_group(mode: str) -> None:
        desk.ledger_group = mode
        show = getattr(desk, "show_ledger_body", None)
        if callable(show):
            show("projects" if mode == "project" else "table")
        if hasattr(desk, "ledger_refresh"):
            desk.ledger_refresh()

    for mode, label in _GROUPS:
        _button(tk, parent, label, lambda m=mode: set_group(m)).pack(side="left", padx=2, pady=8)

    entry = tk.Entry(
        parent,
        textvariable=desk.query,
        bg=_BTN,
        fg=_FG,
        insertbackground=_FG,
        relief="flat",
        font=("Segoe UI", -13),
        width=24,
        highlightthickness=0,
        bd=0,
    )
    entry.pack(side="left", padx=(12, 4), pady=8, ipady=3)

    def on_return(_event=None):
        if hasattr(desk, "_run_find"):
            desk._run_find()

    entry.bind("<Return>", on_return)

    def do_print() -> None:
        if hasattr(desk, "root") and hasattr(desk.root, "update"):
            desk.root.update()
        if hasattr(desk, "_say"):
            desk._say("Print uses the window.", "")

    _button(tk, parent, "Print", do_print).pack(side="left", padx=2, pady=8)

    def show_calendar() -> None:
        show = getattr(desk, "show_ledger_body", None)
        if callable(show):
            show("calendar")

    _button(tk, parent, "Calendar", show_calendar).pack(side="left", padx=2, pady=8)

    menu = tk.Menu(
        parent,
        tearoff=0,
        bg=_BTN,
        fg=_FG,
        activebackground=_BG,
        activeforeground=_FG,
        relief="flat",
        bd=0,
    )
    for label, name in _MORE:
        menu.add_command(label=label, command=lambda n=name: _call(desk, n))

    def open_more() -> None:
        x = more.winfo_rootx()
        y = more.winfo_rooty() + more.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    more = _button(tk, parent, "More", open_more)
    more.pack(side="left", padx=(2, 12), pady=8)
