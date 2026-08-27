"""Feedback controls extracted and adapted from the previous UI."""

import tkinter as tk

from ..theme import COLORS


class ToolTip:
    """Contextual help extracted directly from the legacy widget."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip_window = widget, text, None
        widget.bind("<Enter>", self.show_tip, add="+")
        widget.bind("<Leave>", self.hide_tip, add="+")

    def show_tip(self, _event=None):
        text = self.text() if callable(self.text) else self.text
        if self.tip_window or not text:
            return
        x, y = self.widget.winfo_rootx() + 20, self.widget.winfo_rooty() + 20
        self.tip_window = tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, justify=tk.LEFT, background=COLORS["surface_alt"], foreground=COLORS["text"], relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9), wraplength=420).pack(ipadx=5, ipady=3)

    def hide_tip(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None
