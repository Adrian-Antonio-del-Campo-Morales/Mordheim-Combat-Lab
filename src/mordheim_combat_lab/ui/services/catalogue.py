"""Presentation-oriented knowledge-base queries with no Tkinter dependency."""

from __future__ import annotations

from dataclasses import dataclass

from ...catalog.loader import BandPackage, load_bands, load_collections, load_mechanics, load_runtime_scope, load_simulation_mappings, load_skills


@dataclass(frozen=True, slots=True)
class ProfileChoice:
    collection: str
    band_id: str
    profile_id: str
    name: str


@dataclass(frozen=True, slots=True)
class SkillChoice:
    id: str
    name: str
    category: str
    summary: str


@dataclass(frozen=True, slots=True)
class ProfileRule:
    id: str
    name: str
    effect: str
    runtime_grant: bool


class CombatCatalogue:
    """Small index used by the new UI selectors."""

    def __init__(self, ruleset: str = "mordheim"):
        self.ruleset = ruleset
        self._packages = {
            (package.collection, str(package.band["id"])): package
            for collection in load_collections()
            if ruleset in collection.get("rulesets", ())
            for package in load_bands(str(collection["id"]))
            if package.ruleset == ruleset
        }
        self._mechanics = {
            str(row["id"]): row
            for family in ("weapons", "defences", "armours", "materials", "preparations", "poisons")
            for row in load_mechanics(ruleset).get(family, ())
        }
        self._excluded_mechanics = {
            str(row["id"])
            for row in load_runtime_scope(ruleset).get("mechanic_exclusions") or ()
        }
        option_to_id = {str(row.get("engine_option")): item_id for item_id, row in self._mechanics.items()}
        self._item_mechanics = {
            str(row["item_id"]): option_to_id[str(row["engine_option"])]
            for row in load_simulation_mappings(ruleset).get("item_mappings", ())
            if row.get("status") == "implemented" and str(row.get("engine_option")) in option_to_id
        }
        self._global_costs = self._costs_for_packages(tuple(self._packages.values()))

    def collections(self) -> tuple[tuple[str, str], ...]:
        return tuple((str(row["id"]), str(row.get("name") or row["id"])) for row in load_collections() if self.ruleset in row.get("rulesets", ()))

    def bands(self, collection: str, categories: set[str] | None = None) -> tuple[BandPackage, ...]:
        """Return bands in a collection, optionally filtered by source grade.

        Categories are KB metadata (``core``, ``1a``, ``1b``, ``1c`` and
        ``trollheim``), rather than a second catalogue.  This lets the legacy
        collections picker filter the same stable profile IDs used by runtime.
        """
        selected = {value.casefold() for value in categories or ()}
        return tuple(
            package for (package_collection, _), package in self._packages.items()
            if package_collection == collection
            and (not selected or selected.intersection({str(value).casefold() for value in package.band.get("categories") or ()}))
        )

    def bands_for_categories(self, categories: set[str] | None = None) -> tuple[BandPackage, ...]:
        """Return executable bands from every enabled legacy collection grade."""
        return tuple(package for collection, _name in self.collections() for package in self.bands(collection, categories))

    def profiles(self, collection: str, band_id: str) -> tuple[ProfileChoice, ...]:
        package = self._packages[(collection, band_id)]
        return tuple(ProfileChoice(collection, band_id, str(row["id"]), str(row["name"])) for row in package.profiles)

    def profile(self, choice: ProfileChoice) -> dict:
        """Return profile data for display, not editable UI state."""
        package = self._packages[(choice.collection, choice.band_id)]
        return next(row for row in package.profiles if row["id"] == choice.profile_id)

    def mechanic(self, mechanic_id: str) -> dict:
        """Return the normalized mechanic metadata used for UI constraints."""
        return self._mechanics[mechanic_id]

    def skills(self, choice: ProfileChoice | None) -> tuple[SkillChoice, ...]:
        """Return profile-legal skills, or every executable skill for free selection."""
        profile = self.profile(choice) if choice else None
        allowed_categories = set(profile.get("skill_access") or ()) if profile else None
        return tuple(
            SkillChoice(str(skill["id"]), str(skill["name"]), str(skill["category"]), str(skill.get("summary") or ""))
            for skill in load_skills(self.ruleset)
            if self._skill_is_legal_for_profile(skill, choice, allowed_categories)
            and skill.get("id") not in self._excluded_mechanics
        )

    def _skill_is_legal_for_profile(self, skill: dict, choice: ProfileChoice | None, allowed_categories: set[str] | None) -> bool:
        """Filter special skills by their warband source instead of its shared category."""
        category = str(skill.get("category") or "")
        if allowed_categories is None:
            return True
        if category not in allowed_categories:
            return False
        if category != "special":
            return True
        # Trollheim variants retain the canonical Mordheim family in the KB,
        # so a skill source can legitimately cite that canonical band id.
        source_ids = {choice.band_id, str(self._packages[(choice.collection, choice.band_id)].band.get("canonical_family") or "")}
        return any(
            any(f"/{band_id}" in str(reference.get("url") or "") for band_id in source_ids if band_id)
            for reference in skill.get("source_refs") or ()
        )

    def profile_rules(self, choice: ProfileChoice | None) -> tuple[ProfileRule, ...]:
        """Return editorial profile rules together with their runtime status."""
        if choice is None:
            return ()
        package = self._packages[(choice.collection, choice.band_id)]
        profile = self.profile(choice)
        rule_ids = set(profile.get("rule_ids") or ())
        return tuple(
            ProfileRule(
                str(rule["id"]),
                str(rule["name"]),
                str(rule.get("effect") or ""),
                bool(
                    (rule.get("runtime") or {}).get("implemented") == "YES"
                    and (rule.get("runtime") or {}).get("grant") in {"profile", "band"}
                ),
            )
            for rule in package.special_rules
            if rule.get("id") in rule_ids
        )

    def weapons(self, choice: ProfileChoice | None) -> tuple[tuple[str, str], ...]:
        return self._equipment(choice, "weapons", lambda row: row.get("main_hand"))

    def off_hand_options(self, choice: ProfileChoice | None) -> tuple[tuple[str | None, str], ...]:
        options = self._equipment(
            choice,
            ("weapons", "defences"),
            lambda row: row.get("off_hand") or row.get("id") in {"defence.shield", "defence.buckler", "defence.kite-shield"},
        )
        return ((None, "Free hand"), *options)

    def armours(self, choice: ProfileChoice | None) -> tuple[tuple[str, str], ...]:
        return (("armour.no-armour", "No armour"), *self._equipment(choice, "armours", lambda _row: True))

    def helmets(self, choice: ProfileChoice | None) -> tuple[tuple[str | None, str], ...]:
        options = self._equipment(
            choice,
            "defences",
            lambda row: row.get("id") in {"defence.helmet", "defence.cooking-pot-helmet"},
        )
        return ((None, "No helmet"), *options)

    def materials(self, choice: ProfileChoice | None) -> tuple[tuple[str, str], ...]:
        return (("material.normal", "Normal"), *self._equipment(choice, "materials", lambda _row: True))

    def preparations(self, choice: ProfileChoice | None) -> tuple[tuple[str | None, str], ...]:
        return ((None, "No preparation"), *self._equipment(choice, "preparations", lambda _row: True))

    def poisons(self, choice: ProfileChoice | None) -> tuple[tuple[str | None, str], ...]:
        return ((None, "No poison"), *self._equipment(choice, "poisons", lambda _row: True))

    def cost(self, mechanic_id: str | None, choice: ProfileChoice | None) -> float | None:
        """Lowest legal acquisition cost for one executable mechanic."""
        if mechanic_id is None or mechanic_id in {"armour.no-armour", "material.normal"}:
            return 0.0
        if choice is None:
            return self._global_costs.get(mechanic_id)
        package = self._packages[(choice.collection, choice.band_id)]
        profile = self.profile(choice)
        allowed_lists = set(profile.get("equipment_lists") or ())
        costs = self._costs_for_packages((package,), allowed_lists)
        return costs.get(mechanic_id, self._global_costs.get(mechanic_id))

    def _costs_for_packages(self, packages: tuple[BandPackage, ...], allowed_lists: set[str] | None = None) -> dict[str, float]:
        costs: dict[str, float] = {}
        for package in packages:
            for equipment_list in package.equipment_lists:
                if allowed_lists is not None and str(equipment_list.get("id")) not in allowed_lists:
                    continue
                for item in equipment_list.get("items") or ():
                    mechanic_id = self._item_mechanics.get(str(item.get("item_id")))
                    cost = item.get("cost")
                    if mechanic_id is None or not isinstance(cost, (int, float)):
                        continue
                    costs[mechanic_id] = min(costs.get(mechanic_id, float(cost)), float(cost))
        return costs

    def _equipment(self, choice, families, allowed) -> tuple[tuple[str, str], ...]:
        return self._profile_equipment(choice, families, allowed) if choice else self._runtime_equipment(families, allowed)

    def _profile_equipment(self, choice: ProfileChoice, families, allowed) -> tuple[tuple[str, str], ...]:
        package = self._packages[(choice.collection, choice.band_id)]
        profile = next(row for row in package.profiles if row["id"] == choice.profile_id)
        lists = {str(row["id"]): row for row in package.equipment_lists}
        item_ids = set(profile.get("fixed_equipment") or ())
        for list_id in profile.get("equipment_lists") or ():
            item_ids.update(str(row["item_id"]) for row in lists[str(list_id)].get("items") or ())
        if isinstance(families, str):
            families = (families,)
        prefixes = tuple({"weapons": "weapon.", "defences": "defence.", "armours": "armour.", "materials": "material.", "preparations": "preparation.", "poisons": "poison."}[family] for family in families)
        result = {
            self._item_mechanics[item_id]
            for item_id in item_ids
            if item_id in self._item_mechanics
            and self._item_mechanics[item_id].startswith(prefixes)
            and allowed(self._mechanics[self._item_mechanics[item_id]])
        }
        return tuple(sorted(((item_id, str(self._mechanics[item_id]["name"])) for item_id in result), key=lambda item: item[1]))

    def _runtime_equipment(self, families, allowed) -> tuple[tuple[str, str], ...]:
        if isinstance(families, str):
            families = (families,)
        prefixes = tuple({"weapons": "weapon.", "defences": "defence.", "armours": "armour.", "materials": "material.", "preparations": "preparation.", "poisons": "poison."}[family] for family in families)
        result = {
            item_id for item_id, row in self._mechanics.items()
            if item_id.startswith(prefixes) and item_id not in self._excluded_mechanics and allowed(row)
        }
        return tuple(sorted(((item_id, str(self._mechanics[item_id]["name"])) for item_id in result), key=lambda item: item[1]))
