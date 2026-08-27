"""Knowledge-base driven skill-improvement comparison tab."""

from __future__ import annotations

from dataclasses import replace
import threading
from tkinter import StringVar
from tkinter import ttk

from ...core.compiler import compile_fighter
from ...core.engine import simulate_duel
from ...core.models import SimulationCancelled
from ..widgets import AnalysisProgress


class ImprovementAnalysisTab(ttk.Frame):
    """Compare each selectable additional skill against the current build."""

    def __init__(self, parent, catalogue, candidate_editor, enemy_editor, settings_provider):
        super().__init__(parent, padding=12)
        self.catalogue = catalogue
        self.candidate_editor = candidate_editor
        self.enemy_editor = enemy_editor
        self.settings_provider = settings_provider
        self.status = StringVar(value="Compare each legal additional skill against the candidate baseline.")
        self._running = False
        self._build_gui()

    def _build_gui(self) -> None:
        ttk.Label(self, text="Improvement analysis", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Each result adds one currently unselected, profile-legal skill to the candidate configuration.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        self.run_button = ttk.Button(self, text="Compare improvements", style="Accent.TButton", command=self.run)
        self.run_button.pack(anchor="w", pady=(0, 10))
        self.progress = AnalysisProgress(self)
        self.progress.pack(fill="x", pady=(0, 10))
        columns = ("skill", "candidate", "impact", "enemy", "unresolved")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        definitions = (("skill", "Skill", 280), ("candidate", "Candidate win", 145), ("impact", "Impact", 120), ("enemy", "Enemy win", 145), ("unresolved", "Unresolved", 130))
        for column, heading, width in definitions:
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="w" if column == "skill" else "center")
        self.tree.pack(fill="both", expand=True)
        ttk.Label(self, textvariable=self.status, style="Muted.TLabel", wraplength=1080).pack(anchor="w", pady=(10, 0))

    def run(self) -> None:
        if self._running:
            return
        try:
            settings = self.settings_provider()
            candidate = self.candidate_editor.build()
            enemy = self.enemy_editor.build()
            selected = set(candidate.skill_ids)
            skills = tuple(skill for skill in self.catalogue.skills(self.candidate_editor.choice) if skill.id not in selected)
        except (KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Configuration error: {exc}")
            return
        self._running = True
        self.run_button.configure(state="disabled")
        self.status.set(f"Comparing {len(skills)} additional skills…")
        cancel_event = self.progress.start(len(skills) + 1)
        threading.Thread(target=self._compare, args=(candidate, enemy, skills, settings, cancel_event), daemon=True).start()

    def _compare(self, candidate, enemy, skills, settings, cancel_event) -> None:
        try:
            compiled_enemy = compile_fighter(enemy)
            baseline = simulate_duel(settings.request(compile_fighter(candidate), compiled_enemy, cancel_event))
            self.after(0, self.progress.advance, 1)
            rows = []
            for completed, skill in enumerate(skills, start=2):
                if cancel_event.is_set():
                    raise SimulationCancelled()
                fighter = compile_fighter(replace(candidate, skill_ids=(*candidate.skill_ids, skill.id)))
                result = simulate_duel(settings.request(fighter, compiled_enemy, cancel_event))
                rows.append((skill.name, result.first_win_rate, result.first_win_rate - baseline.first_win_rate, result.second_win_rate, result.unresolved_rate))
                self.after(0, self.progress.advance, completed)
        except SimulationCancelled:
            self.after(0, self._cancelled)
        except Exception as exc:
            self.after(0, self._failed, str(exc))
        else:
            self.after(0, self._finished, rows, baseline.first_win_rate, settings.simulations)

    def _finished(self, rows, baseline: float, simulations: int) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for skill, candidate, impact, enemy, unresolved in sorted(rows, key=lambda row: row[2], reverse=True):
            self.tree.insert("", "end", values=(skill, f"{candidate:.2f}%", f"{impact:+.2f}%", f"{enemy:.2f}%", f"{unresolved:.2f}%"))
        self.status.set(f"Baseline: {baseline:.2f}% candidate win rate. Compared {len(rows)} skills across {(len(rows) + 1) * simulations:,} duels.")
        self.progress.finish("Complete")
        self._done()

    def _failed(self, error: str) -> None:
        self.status.set(f"Improvement analysis error: {error}")
        self.progress.finish("Error")
        self._done()

    def _cancelled(self) -> None:
        self.status.set("Improvement analysis cancelled.")
        self.progress.finish("Cancelled")
        self._done()

    def _done(self) -> None:
        self._running = False
        self.run_button.configure(state="normal")
