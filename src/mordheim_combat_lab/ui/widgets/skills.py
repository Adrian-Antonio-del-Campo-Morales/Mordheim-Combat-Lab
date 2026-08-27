"""Shared skills checklist adapted from the legacy warrior editor."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .feedback import ToolTip


class SkillChecklist(ttk.Frame):
    """A grouped, reusable skill selector backed by ``BooleanVar`` values."""

    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.variables: dict[str, tk.BooleanVar] = {}
        self._build_empty_state()

    def _build_empty_state(self) -> None:
        self.empty = ttk.Label(self, text="No selectable skills are available for this profile.", style="Card.Muted.TLabel")
        self.empty.pack(anchor="w")

    def set_skills(self, skills) -> None:
        for widget in self.winfo_children():
            widget.destroy()
        self.variables = {}
        grouped: dict[str, list] = {}
        for skill in skills:
            grouped.setdefault(skill.category.capitalize(), []).append(skill)
        if not grouped:
            self._build_empty_state()
            return
        for column, (category, entries) in enumerate(sorted(grouped.items())):
            self.columnconfigure(column, weight=1, uniform="skill-categories")
            panel = ttk.LabelFrame(self, text=category, padding=(8, 5))
            panel.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 4), pady=2)
            for row, skill in enumerate(entries):
                variable = tk.BooleanVar(value=False)
                variable.trace_add("write", self._changed)
                self.variables[skill.id] = variable
                check = ttk.Checkbutton(panel, text=skill.name, variable=variable)
                check.grid(row=row, column=0, sticky="w", pady=1)
                ToolTip(check, skill.summary)

    def selected_ids(self) -> tuple[str, ...]:
        return tuple(skill_id for skill_id, variable in self.variables.items() if variable.get())

    def _changed(self, *_args) -> None:
        if self.on_change:
            self.on_change()
