"""Knowledge-base driven armour and off-hand comparison tab."""

from __future__ import annotations

from dataclasses import replace
from itertools import product
import threading
from tkinter import IntVar, StringVar
from tkinter import ttk

from ...core.compiler import compile_fighter
from ...core.engine import simulate_duel
from ...core.models import SimulationCancelled
from ..widgets import AnalysisProgress


class EquipmentAnalysisTab(ttk.Frame):
    """Compare legal armour and off-hand combinations against the current enemy."""

    MAX_CONFIGURATIONS = 500

    def __init__(self, parent, catalogue, candidate_editor, enemy_editor, settings_provider):
        super().__init__(parent, padding=12)
        self.catalogue = catalogue
        self.candidate_editor = candidate_editor
        self.enemy_editor = enemy_editor
        self.settings_provider = settings_provider
        self.maximum_changed_slots = IntVar(value=1)
        self.status = StringVar(value="Compare the candidate's legal off-hand and armour configurations.")
        self._running = False
        self._build_gui()

    def _build_gui(self) -> None:
        ttk.Label(self, text="Equipment analysis", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="The selected main weapon and skills remain fixed while legal equipment configurations are simulated.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 10))
        self.run_button = ttk.Button(controls, text="Compare equipment", style="Accent.TButton", command=self.run)
        self.run_button.pack(side="left")
        ttk.Label(controls, text="Maximum changed slots").pack(side="left", padx=(14, 5))
        ttk.Spinbox(controls, from_=1, to=8, textvariable=self.maximum_changed_slots, width=5).pack(side="left")
        self.progress = AnalysisProgress(self)
        self.progress.pack(fill="x", pady=(0, 10))
        columns = ("equipment", "candidate", "enemy", "unresolved")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        definitions = (("equipment", "Equipment configuration", 570), ("candidate", "Candidate win", 145), ("enemy", "Enemy win", 145), ("unresolved", "Unresolved", 130))
        for column, heading, width in definitions:
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="w" if column == "equipment" else "center")
        self.tree.pack(fill="both", expand=True)
        ttk.Label(self, textvariable=self.status, style="Muted.TLabel", wraplength=1080).pack(anchor="w", pady=(10, 0))

    def run(self) -> None:
        if self._running:
            return
        try:
            settings = self.settings_provider()
            candidate = self.candidate_editor.build()
            enemy = self.enemy_editor.build()
            configurations = self._configurations(candidate)
        except (KeyError, TypeError, ValueError) as exc:
            self.status.set(f"Configuration error: {exc}")
            return
        if len(configurations) > self.MAX_CONFIGURATIONS:
            self.status.set(f"{len(configurations):,} configurations exceed the {self.MAX_CONFIGURATIONS:,} safety limit. Reduce maximum changed slots.")
            return
        self._running = True
        self.run_button.configure(state="disabled")
        self.status.set(f"Comparing {len(configurations)} equipment configurations…")
        cancel_event = self.progress.start(len(configurations))
        threading.Thread(target=self._compare, args=(candidate, enemy, configurations, settings, cancel_event), daemon=True).start()

    def _configurations(self, candidate) -> tuple[tuple[dict, str], ...]:
        """Build bounded variations across every equipment slot supported by the editor."""
        choice = self.candidate_editor.choice
        helmet = candidate.defence_ids[0] if candidate.defence_ids else None
        slots = [
            ("Off hand", self.catalogue.off_hand_options(choice), candidate.off_hand_id),
            ("Armour", self.catalogue.armours(choice), candidate.armour_id),
            ("Helmet", self.catalogue.helmets(choice), helmet),
            ("Main material", self.catalogue.materials(choice), candidate.main_material_id),
            ("Preparation", self.catalogue.preparations(choice), candidate.preparation_ids[0] if candidate.preparation_ids else None),
            ("Main poison", self.catalogue.poisons(choice), candidate.main_poison_id),
        ]
        if self.catalogue.mechanic(candidate.main_weapon_id).get("hands") == 2:
            slots[0] = ("Off hand", ((None, "Free hand"),), None)
        maximum = int(self.maximum_changed_slots.get())
        values = [options for _name, options, _baseline in slots]
        configurations = []
        for selected in product(*values):
            selected_ids = tuple(item_id for item_id, _name in selected)
            off_hand_id = selected_ids[0]
            off_slots = (
                ("Off-hand material", self.catalogue.materials(choice), candidate.off_material_id),
                ("Off-hand poison", self.catalogue.poisons(choice), candidate.off_poison_id),
            ) if off_hand_id and off_hand_id.startswith("weapon.") else (
                ("Off-hand material", (("material.normal", "Normal"),), "material.normal"),
                ("Off-hand poison", ((None, "No poison"),), None),
            )
            for off_selected in product(*(options for _name, options, _baseline in off_slots)):
                all_slots = (*slots, *off_slots)
                all_ids = (*selected_ids, *(item_id for item_id, _name in off_selected))
                changes = sum(item_id != baseline for item_id, (_name, _options, baseline) in zip(all_ids, all_slots))
                if changes > maximum:
                    continue
                selected_names = (*(name for _item_id, name in selected), *(name for _item_id, name in off_selected))
                updates = {
                    "off_hand_id": all_ids[0],
                    "armour_id": all_ids[1],
                    "defence_ids": tuple(item_id for item_id in (all_ids[2],) if item_id),
                    "main_material_id": all_ids[3],
                    "preparation_ids": tuple(item_id for item_id in (all_ids[4],) if item_id),
                    "main_poison_id": all_ids[5],
                    "off_material_id": all_ids[6],
                    "off_poison_id": all_ids[7],
                }
                labels = [f"{name}: {value}" for (name, _options, _baseline), value in zip(all_slots, selected_names)]
                configurations.append((updates, " · ".join(labels)))
        return tuple(configurations)

    def _compare(self, candidate, enemy, configurations, settings, cancel_event) -> None:
        try:
            compiled_enemy = compile_fighter(enemy)
            rows = []
            skipped = 0
            for completed, (updates, label) in enumerate(configurations, start=1):
                if cancel_event.is_set():
                    raise SimulationCancelled()
                try:
                    fighter = compile_fighter(replace(candidate, **updates))
                except (KeyError, TypeError, ValueError):
                    skipped += 1
                    self.after(0, self.progress.advance, completed)
                    continue
                result = simulate_duel(settings.request(fighter, compiled_enemy, cancel_event))
                rows.append((label, result.first_win_rate, result.second_win_rate, result.unresolved_rate))
                self.after(0, self.progress.advance, completed)
        except SimulationCancelled:
            self.after(0, self._cancelled)
        except Exception as exc:
            self.after(0, self._failed, str(exc))
        else:
            self.after(0, self._finished, rows, skipped, settings.simulations)

    def _finished(self, rows, skipped: int, simulations: int) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for equipment, candidate, enemy, unresolved in sorted(rows, key=lambda row: row[1], reverse=True):
            self.tree.insert("", "end", values=(equipment, f"{candidate:.2f}%", f"{enemy:.2f}%", f"{unresolved:.2f}%"))
        skipped_message = f" Skipped {skipped} invalid configurations." if skipped else ""
        self.status.set(f"Compared {len(rows)} configurations across {len(rows) * simulations:,} duels.{skipped_message}")
        self.progress.finish("Complete")
        self._done()

    def _failed(self, error: str) -> None:
        self.status.set(f"Equipment analysis error: {error}")
        self.progress.finish("Error")
        self._done()

    def _cancelled(self) -> None:
        self.status.set("Equipment analysis cancelled.")
        self.progress.finish("Cancelled")
        self._done()

    def _done(self) -> None:
        self._running = False
        self.run_button.configure(state="normal")
