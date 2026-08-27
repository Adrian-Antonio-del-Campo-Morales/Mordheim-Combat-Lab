"""Knowledge-base driven weapon comparison tab."""

from __future__ import annotations

from dataclasses import replace
import threading
from tkinter import StringVar
from tkinter import ttk

from ...core.compiler import compile_fighter
from ...core.engine import simulate_duel
from ...core.models import SimulationCancelled
from ..widgets import AnalysisProgress


class WeaponAnalysisTab(ttk.Frame):
    """Compare every legal candidate weapon against the configured enemy."""

    def __init__(self, parent, catalogue, candidate_editor, enemy_editor, settings_provider):
        super().__init__(parent, padding=12)
        self.catalogue = catalogue
        self.candidate_editor = candidate_editor
        self.enemy_editor = enemy_editor
        self.settings_provider = settings_provider
        self.status = StringVar(value="Configure the duel, then compare the candidate's legal weapons.")
        self._running = False
        self._build_gui()

    def _build_gui(self) -> None:
        ttk.Label(self, text="Weapon analysis", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Each legal main weapon is simulated against the current enemy configuration.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 10))
        self.run_button = ttk.Button(controls, text="Compare weapons", style="Accent.TButton", command=self.run)
        self.run_button.pack(side="left")
        self.progress = AnalysisProgress(self)
        self.progress.pack(fill="x", pady=(0, 10))
        columns = ("weapon", "candidate", "enemy", "unresolved")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        for column, heading, width in (("weapon", "Weapon", 300), ("candidate", "Candidate win", 150), ("enemy", "Enemy win", 150), ("unresolved", "Unresolved", 130)):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="w" if column == "weapon" else "center")
        self.tree.pack(fill="both", expand=True)
        ttk.Label(self, textvariable=self.status, style="Muted.TLabel", wraplength=1080).pack(anchor="w", pady=(10, 0))

    def run(self) -> None:
        if self._running:
            return
        try:
            settings = self.settings_provider()
            candidate = self.candidate_editor.build()
            enemy = self.enemy_editor.build()
            options = self.candidate_editor.main_weapon_options()
            if not options:
                raise ValueError("At least one legal weapon is required.")
        except (KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Configuration error: {exc}")
            return
        self._running = True
        self.run_button.configure(state="disabled")
        self.status.set(f"Comparing {len(options)} weapons with {settings.simulations:,} duels each…")
        cancel_event = self.progress.start(len(options))
        threading.Thread(target=self._compare, args=(candidate, enemy, options, settings, cancel_event), daemon=True).start()

    def _compare(self, candidate, enemy, options, settings, cancel_event) -> None:
        try:
            compiled_enemy = compile_fighter(enemy)
            rows = []
            for completed, (weapon_id, name) in enumerate(options, start=1):
                if cancel_event.is_set():
                    raise SimulationCancelled()
                off_hand = candidate.off_hand_id
                if self.catalogue.mechanic(weapon_id).get("hands") == 2:
                    off_hand = None
                fighter = compile_fighter(replace(candidate, main_weapon_id=weapon_id, off_hand_id=off_hand))
                result = simulate_duel(settings.request(fighter, compiled_enemy, cancel_event))
                rows.append((name, result.first_win_rate, result.second_win_rate, result.unresolved_rate))
                self.after(0, self.progress.advance, completed)
        except SimulationCancelled:
            self.after(0, self._cancelled)
        except Exception as exc:
            self.after(0, self._failed, str(exc))
        else:
            self.after(0, self._finished, rows, settings.simulations)

    def _finished(self, rows, simulations: int) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, candidate, enemy, unresolved in sorted(rows, key=lambda row: row[1], reverse=True):
            self.tree.insert("", "end", values=(name, f"{candidate:.2f}%", f"{enemy:.2f}%", f"{unresolved:.2f}%"))
        self.status.set(f"Compared {len(rows)} weapons across {len(rows) * simulations:,} duels.")
        self.progress.finish("Complete")
        self._done()

    def _failed(self, error: str) -> None:
        self.status.set(f"Weapon analysis error: {error}")
        self.progress.finish("Error")
        self._done()

    def _cancelled(self) -> None:
        self.status.set("Weapon analysis cancelled.")
        self.progress.finish("Cancelled")
        self._done()

    def _done(self) -> None:
        self._running = False
        self.run_button.configure(state="normal")
