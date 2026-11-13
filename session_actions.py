"""Session-band actions from the old desk. Not a separate page."""

from __future__ import annotations


_BG = "#07080A"
_ELEVATED = "#181C26"
_LINE = "#2A3140"
_INK = "#E8ECF4"
_ACCENT = "#7C9CFF"
_FONT = ("Segoe UI", -15)

_ACTIONS = (
    ("Load", "_on_load"),
    ("Preview", "_on_preview"),
    ("Import", "_on_import"),
    ("Export", "_on_export"),
    ("Index", "_on_index"),
    ("Formats", "_on_formats"),
    ("Anonymize", "_on_anonymize"),
    ("Check recovery", "_on_recover"),
    ("Restore", "_on_restore"),
    ("Check strip", "_on_strip_dry"),
    ("Write strip", "_on_strip"),
    ("Name", "_on_name"),
)


def build(parent, desk) -> None:
    tk = desk.tk
    row = tk.Frame(parent, bg=_BG)
    row.pack(fill="x")
    buttons = []
    for label, name in _ACTIONS:
        if not hasattr(desk, name):
            continue
        buttons.append(tk.Button(
            row,
            text=label,
            command=getattr(desk, name),
            bg=_ELEVATED,
            fg=_INK,
            activebackground="#1E2430",
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
        ))
    state = {"width": 0, "buttons": buttons, "row": row}

    def reflow(event=None) -> None:
        if event is not None and event.widget is not row:
            return
        width = row.winfo_width()
        if width < 80:
            width = 700
        if abs(width - state["width"]) < 24:
            return
        state["width"] = width
        # Simple flow: place left to right, wrapping by measured widths.
        for button in buttons:
            button.grid_forget()
        r = c = 0
        x = 0
        for button in buttons:
            button.update_idletasks()
            need = button.winfo_reqwidth() + 6
            if x and x + need > width:
                r += 1
                c = 0
                x = 0
            button.grid(row=r, column=c, padx=(0, 6), pady=4, sticky="w")
            c += 1
            x += need

    row.bind("<Configure>", reflow)
    for button in buttons:
        button.grid(row=0, column=buttons.index(button), padx=(0, 6), pady=4, sticky="w")
    row.after(50, reflow)


def fill(desk, hit) -> None:
    return None


def refresh(desk, hits) -> None:
    return None
