"""Composition root for the new Tkinter application."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, ttk

from ..core.compiler import compile_fighter
from ..core.engine import simulate_duel
from .editors import FighterEditor
from .services import CombatCatalogue, DuelExecutionSettings
from .tabs import EquipmentAnalysisTab, ImprovementAnalysisTab, WeaponAnalysisTab
from .theme import apply_theme
from .widgets import DuelResultCards
from .preferences import load_preferences, save_preferences
from .workbooks import CombatLabWorkbookError, load_ui_workbook, save_workbook


def _preference_int(preferences: dict, key: str, default: int, minimum: int = 0) -> int:
    """Read a bounded integer preference without making startup fragile."""
    try:
        value = int(preferences.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


class CombatLabApp(tk.Tk):
    """KB-driven application shell with the legacy workbook layout.

    The original application deliberately separated configuring the candidate,
    configuring enemies and reviewing each analysis.  Keeping that information
    architecture is important: a "Duel" page with two anonymous cards made
    the new runtime feel like a different product.  The widgets below are new
    views over :class:`FighterBuild`, not adapters for ``legacy_ui``.
    """

    def __init__(self):
        super().__init__()
        apply_theme(self)
        self.title("Mordheim Combat Lab")
        self.minsize(900, 700)
        self._preferences = load_preferences()
        self.geometry(str(self._preferences.get("window_geometry") or "1180x800"))
        self.catalogue = CombatCatalogue()
        self.collection_categories = {
            category: tk.BooleanVar(value=True)
            for category in ("core", "1a", "1b", "1c", "trollheim")
        }
        self.simulations = tk.IntVar(value=_preference_int(self._preferences, "simulations", 100_000, 1))
        self.seed = tk.IntVar(value=_preference_int(self._preferences, "seed", 0))
        self.batch_size = tk.IntVar(value=_preference_int(self._preferences, "batch_size", 100_000, 1))
        self.maximum_rounds = tk.IntVar(value=_preference_int(self._preferences, "maximum_rounds", 50, 1))
        self.status = tk.StringVar(value="Configure the candidate and enemy, then run the simulation.")
        self._running = False
        self._last_result = None
        self._build_gui()
        self._restore_geometry()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_gui(self) -> None:
        header = ttk.Frame(self, padding=(20, 14, 20, 10))
        header.pack(fill="x")
        branding = ttk.Frame(header)
        branding.pack(side="left")
        ttk.Label(branding, text="Mordheim Combat Lab", style="Title.TLabel").pack(anchor="w")
        ttk.Label(branding, text="Simulation Workbook", style="Muted.TLabel").pack(anchor="w")
        actions = ttk.Frame(header)
        actions.pack(side="right")
        self.collections_button = ttk.Menubutton(actions, text="Collections ▾")
        collections_menu = tk.Menu(self.collections_button, tearoff=False)
        for category, label in (("core", "Mordheim Core"), ("1a", "1A"), ("1b", "1B"), ("1c", "1C"), ("trollheim", "Trollheim")):
            collections_menu.add_checkbutton(label=label, variable=self.collection_categories[category], command=self._collections_changed)
        self.collections_button.configure(menu=collections_menu)
        self.collections_button.pack(side="left", padx=(0, 10))
        import_button = ttk.Menubutton(actions, text="Import ▾")
        import_menu = tk.Menu(import_button, tearoff=False)
        import_menu.add_command(label="Load candidate", command=lambda: self._load_workbook("candidate"))
        import_menu.add_command(label="Load enemy", command=lambda: self._load_workbook("enemy"))
        import_button.configure(menu=import_menu)
        import_button.pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Load", command=self._load_workbook).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Save", style="Accent.TButton", command=self._save_workbook).pack(side="left")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        candidate_tab = ttk.Frame(self.notebook, padding=12)
        enemy_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(candidate_tab, text="Candidate")
        self.notebook.add(enemy_tab, text="Enemy")
        self._build_candidate_tab(candidate_tab)
        self._build_enemy_tab(enemy_tab)
        self.notebook.add(ImprovementAnalysisTab(self.notebook, self.catalogue, self.candidate_editor, self.enemy_editor, self.execution_settings), text="Improvements")
        self.notebook.add(WeaponAnalysisTab(self.notebook, self.catalogue, self.candidate_editor, self.enemy_editor, self.execution_settings), text="Weapons")
        self.notebook.add(EquipmentAnalysisTab(self.notebook, self.catalogue, self.candidate_editor, self.enemy_editor, self.execution_settings), text="Equipment")
        rules_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(rules_tab, text="House Rules")
        self._build_rules_tab(rules_tab)

    def _build_candidate_tab(self, parent) -> None:
        ttk.Label(parent, text="Candidate", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Choose a warrior and their legal combat configuration.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        self.candidate_editor = FighterEditor(parent, "Candidate", self.catalogue, self._editor_changed)
        self.candidate_editor.pack(fill="x")
        self.result_cards = DuelResultCards(parent)
        self.result_cards.pack(fill="x", pady=(12, 0))
        controls = ttk.Frame(parent, padding=(0, 14, 0, 0))
        controls.pack(fill="x")
        for label, variable, minimum, maximum, increment in (
            ("Simulations", self.simulations, 1_000, 10_000_000, 10_000),
            ("Seed", self.seed, 0, 2_147_483_647, 1),
            ("Batch size", self.batch_size, 1, 1_000_000, 10_000),
            ("Maximum rounds", self.maximum_rounds, 1, 500, 1),
        ):
            ttk.Label(controls, text=label).pack(side="left", padx=(0, 5))
            ttk.Spinbox(controls, from_=minimum, to=maximum, increment=increment, textvariable=variable, width=10).pack(side="left", padx=(0, 12))
        self.run_button = ttk.Button(controls, text="Run simulation", style="Accent.TButton", command=self._run_simulation)
        self.run_button.pack(side="left")
        self.cancel_button = ttk.Button(controls, text="Cancel", command=self._cancel_simulation, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        ttk.Label(parent, textvariable=self.status, style="Muted.TLabel", wraplength=1080).pack(anchor="w", pady=(10, 0))

    def _build_enemy_tab(self, parent) -> None:
        ttk.Label(parent, text="Enemy", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Configure the opposing warrior used by every simulation and analysis.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        self.enemy_editor = FighterEditor(parent, "Enemy", self.catalogue, self._editor_changed)
        self.enemy_editor.pack(fill="x")

    def _collections_changed(self) -> None:
        """Filter both editor warband lists by the selected KB source grades."""
        categories = {category for category, variable in self.collection_categories.items() if variable.get()}
        self.candidate_editor.set_categories(categories)
        self.enemy_editor.set_categories(categories)

    def _build_rules_tab(self, parent) -> None:
        ttk.Label(parent, text="House Rules", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text=("The executable rules are selected by the knowledge base. "
                  "This version deliberately does not restore the legacy checkboxes: "
                  "they altered the retired engine and could silently produce a duel "
                  "that the new runtime cannot represent."),
            style="Muted.TLabel", wraplength=820, justify="left",
        ).pack(anchor="w", pady=(8, 16))
        ttk.Label(parent, text="Active runtime", style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Mordheim close combat · KB-backed legal equipment · deterministic seed support", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    def _restore_geometry(self) -> None:
        """Use the former centred-window behaviour unless a size was saved."""
        if self._preferences.get("window_geometry"):
            return
        width = min(1280, max(900, self.winfo_screenwidth() - 100))
        height = min(1050, max(700, self.winfo_screenheight() - 30))
        self.geometry(f"{width}x{height}+{max(0, (self.winfo_screenwidth() - width) // 2)}+{max(0, (self.winfo_screenheight() - height) // 2)}")

    def _editor_changed(self) -> None:
        if not self._running:
            self.status.set("Ready to simulate the selected fighters.")

    def _run_simulation(self) -> None:
        if self._running:
            return
        try:
            settings = self.execution_settings()
            first = compile_fighter(self.candidate_editor.build())
            second = compile_fighter(self.enemy_editor.build())
        except (KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Configuration error: {exc}")
            return
        self._running = True
        self._cancel_event = threading.Event()
        self.run_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.status.set(f"Running {settings.simulations:,} simulated duels…")
        threading.Thread(target=self._simulate, args=(first, second, settings, self._cancel_event), daemon=True).start()

    def execution_settings(self) -> DuelExecutionSettings:
        """Snapshot the execution controls for one simulation or analysis run."""
        return DuelExecutionSettings(int(self.simulations.get()), int(self.seed.get()), int(self.batch_size.get()), int(self.maximum_rounds.get()))

    def _cancel_simulation(self) -> None:
        if self._running:
            self._cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.status.set("Cancelling after the current simulation batch…")

    def _simulate(self, first, second, settings, cancel_event) -> None:
        try:
            result = simulate_duel(settings.request(first, second, cancel_event))
        except Exception as exc:
            self.after(0, self._simulation_failed, str(exc))
        else:
            self.after(0, self._simulation_finished, result)

    def _simulation_finished(self, result) -> None:
        self._last_result = result
        self.result_cards.show(result)
        self.status.set(f"Candidate {result.first_win_rate:.2f}% · Enemy {result.second_win_rate:.2f}% · Unresolved {result.unresolved_rate:.2f}% ({result.simulations:,} duels)")
        self._simulation_done()

    def _simulation_failed(self, error: str) -> None:
        self.status.set(f"Simulation error: {error}")
        self._simulation_done()

    def _simulation_done(self) -> None:
        self._running = False
        self.run_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _save_workbook(self) -> None:
        try:
            candidate = self.candidate_editor.build()
            enemy = self.enemy_editor.build()
            settings = self.execution_settings()
        except (KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Configuration error: {exc}")
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Save Mordheim Combat Lab workbook", defaultextension=".xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not path:
            return
        try:
            save_workbook(path, candidate, enemy, settings, self._last_result)
        except OSError as exc:
            self.status.set(f"Workbook save error: {exc}")
        else:
            self.status.set(f"Saved workbook: {path}")

    def _load_workbook(self, target: str = "both") -> None:
        path = filedialog.askopenfilename(parent=self, title="Load Mordheim Combat Lab workbook", filetypes=(("Excel workbook", "*.xlsx"),))
        if not path:
            return
        try:
            candidate, enemy, settings, result = load_ui_workbook(path)
            if target in {"both", "candidate"}:
                self.candidate_editor.load_build(candidate)
            if target in {"both", "enemy"}:
                self.enemy_editor.load_build(enemy)
            if target == "both":
                self.simulations.set(settings.simulations)
                self.seed.set(settings.seed)
                self.batch_size.set(settings.batch_size)
                self.maximum_rounds.set(settings.maximum_rounds)
        except (CombatLabWorkbookError, KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Workbook load error: {exc}")
            return
        self._last_result = result if target == "both" else self._last_result
        if result and target == "both":
            self.result_cards.show(result)
        description = {"both": "workbook", "candidate": "candidate", "enemy": "enemy"}[target]
        self.status.set(f"Loaded {description}: {path}")

    def _close(self) -> None:
        save_preferences({
            "window_geometry": self.geometry(),
            "simulations": self.simulations.get(),
            "seed": self.seed.get(),
            "batch_size": self.batch_size.get(),
            "maximum_rounds": self.maximum_rounds.get(),
        })
        self.destroy()


def main() -> int:
    app = CombatLabApp()
    app.mainloop()
    return 0


__all__ = ["CombatLabApp", "main"]
