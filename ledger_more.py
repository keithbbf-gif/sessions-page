"""More-buttons menu. Desk tools stay on the ledger, not on their own pages."""

from __future__ import annotations

_CARD = "#12151C"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_ACTIVE = "#1E2430"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)
_FONT_MENU = ("Segoe UI", 10)

# Label, desk attribute, arguments. Overview and Formats only explain the ledger.
_ITEMS = (
    ("Refresh", "_load_all", ()),
    ("Build index", "_on_index", ()),
    ("Overview info", "_say", ("Drives and locations stay in the ledger filter.", "")),
    ("Formats", "_say", ("Formats are the source column and the topic column.", "")),
    ("Load", "_on_load", ()),
    ("Import", "_on_import", ()),
    ("Export", "_on_export", ()),
    ("Anonymize", "_on_anonymize", ()),
    ("Check recovery", "_on_recover", ()),
    ("Restore", "_on_restore", ()),
    ("Check strip", "_on_strip_dry", ()),
    ("Write strip", "_on_strip", ()),
    ("Name", "_on_name", ()),
    ("Quit", "_on_quit", ()),
)


def _invoke(desk, name: str, args: tuple) -> None:
    if hasattr(desk, name):
        getattr(desk, name)(*args)


def _post_menu(button, menu) -> None:
    def show() -> None:
        menu.post(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    # After the click, so the button release does not unpost the menu at once.
    button.after(0, show)


def build(parent, desk) -> None:
    tk = desk.tk
    menu = tk.Menu(
        parent,
        tearoff=0,
        bg=_CARD,
        fg=_INK,
        activebackground=_ACTIVE,
        activeforeground=_INK,
        relief="flat",
        bd=0,
        activeborderwidth=0,
        font=_FONT_MENU,
    )
    for label, name, args in _ITEMS:
        if not hasattr(desk, name):
            continue
        menu.add_command(
            label=label,
            command=lambda d=desk, n=name, a=args: _invoke(d, n, a),
            background=_CARD,
            foreground=_INK,
            activebackground=_ACTIVE,
            activeforeground=_INK,
            font=_FONT_MENU,
        )
    button = tk.Button(
        parent,
        text="More buttons",
        bg=_ELEVATED,
        fg=_INK,
        activebackground=_ACTIVE,
        activeforeground=_INK,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=_LINE,
        highlightcolor=_ACCENT,
        font=_FONT,
        padx=10,
        pady=4,
        cursor="hand2",
    )
    button.configure(command=lambda b=button, m=menu: _post_menu(b, m))
    button.pack(side="left", padx=(0, 8))


def refresh(desk, hits) -> None:
    return
