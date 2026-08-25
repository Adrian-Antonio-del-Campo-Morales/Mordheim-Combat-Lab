"""Materialize both source collections into the Combat Lab band contract.

This is intentionally a one-way repository migration. Runtime code consumes the
materialized files and never needs to know which legacy dialect they used.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
BANDS = ROOT / "sources" / "knowledge" / "bands"
SCOPE = ROOT / "sources" / "knowledge" / "index" / "warband-scope.yaml"
CANONICAL_FAMILIES = {
    "trollheim-skaven": "skaven-clan-eshin",
    "trollheim-mercenaries": "mercenaries",
    "trollheim-undead": "undead",
    "trollheim-possessed": "cult-of-the-possessed",
    "trollheim-sisters-of-sigmar": "sisters-of-sigmar",
    "trollheim-witch-hunters": "witch-hunters",
    "lustria-amazonas": "amazons-lustria",
    "lustria-clan-pestilens": "skaven-clan-pestilens",
    "lustria-elfos-oscuros": "dark-elves",
    "lustria-goblins-salvajes": "forest-goblins",
    "lustria-hombres-lagarto": "lizardmen",
    "lustria-norses": "norse-explorers-lustria",
    "lustria-piratas": "pirates",
    "lustria-tileans": "tileans",
    "khemri-guardianes-del-sepulcro": "tomb-guardians",
    "khemri-nomadas": "arabian-tomb-raiders",
    "chaos-streets-dwarf-treasure-hunters": "dwarf-treasure-hunters",
    "chaos-streets-bretonnians": "bretonnian-knights",
    "chaos-streets-sons-of-nagarythe": "shadow-warriors",
    "chaos-streets-pit-fighters": "pit-fighters",
    "chaos-streets-greenskins": "orc-mob",
}


def _translation(value: object, locale: str) -> dict[str, str | None]:
    text = str(value or "").strip()
    return {"en": text if locale == "en" else None, "es": text if locale == "es" else None}


def _localize_records(records: Iterable[dict], locale: str) -> None:
    for record in records:
        if "name" in record:
            record["name_i18n"] = _translation(record["name"], locale)
        if "effect" in record:
            record["effect_i18n"] = _translation(record["effect"], locale)
        _localize_records(record.get("rules") or (), locale)


def _scope_metadata() -> dict[str, dict]:
    raw = yaml.safe_load(SCOPE.read_text(encoding="utf-8"))
    return {str(row["id"]): row for row in raw.get("warbands") or ()}


def _setting_for_trollheim(band_id: str) -> str:
    if band_id.startswith("lustria-"):
        return "Lustria"
    if band_id.startswith("khemri-"):
        return "Khemri"
    if band_id.startswith("caos-en-las-calles-"):
        return "Chaos on the Streets"
    return "Mordheim"


def normalize(path: Path, scope: dict[str, dict]) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") == 1 and "sources" in raw:
        band_id = str(raw["id"])
        expected = CANONICAL_FAMILIES.get(band_id, band_id)
        if raw.get("canonical_family") != expected:
            raw["canonical_family"] = expected
            path.write_text(
                yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=120),
                encoding="utf-8",
            )
        return
    collection = path.parent.name
    locale = "en" if collection == "mordheimer" else "es"
    scoped = scope.get(str(raw["id"]), {})
    old_source = dict(raw.pop("source", {}) or {})
    source_url = old_source.pop("url", None)
    if source_url:
        old_source["url"] = source_url

    grade = raw.pop("grade", None)
    status = raw.pop("status", "source-normalized")
    source_sections = raw.pop("source_sections", []) or []
    categories = [grade] if grade else []
    if collection == "trollheim":
        categories.append("trollheim")

    canonical = {
        "schema_version": 1,
        "id": str(raw.pop("id")),
        "name": str(raw.pop("name")),
        "name_i18n": {},
    }
    # ``raw['name']`` was consumed above; build the translation from the stable
    # canonical value rather than relying on YAML key order.
    canonical["name_i18n"] = _translation(canonical["name"], locale)
    canonical["canonical_family"] = CANONICAL_FAMILIES.get(canonical["id"], canonical["id"])
    canonical.update({
        "original_locale": locale,
        "categories": categories,
        "collections": [collection],
        "grade": grade,
        "setting": scoped.get("setting") or (
            _setting_for_trollheim(canonical["id"]) if collection == "trollheim" else None
        ),
        "publication": scoped.get("publication") or old_source.get("manual"),
        "status": status,
        "sources": [old_source],
        "roster": raw.pop("roster"),
        "equipment_lists": raw.pop("equipment_lists", []) or [],
        "profiles": raw.pop("profiles", []) or [],
        "band_rules": raw.pop("band_rules", []) or [],
        "source_sections": source_sections,
    })
    if raw:
        raise ValueError(f"Unsupported top-level keys in {path}: {sorted(raw)}")

    _localize_records(canonical["equipment_lists"], locale)
    _localize_records(canonical["profiles"], locale)
    _localize_records(canonical["band_rules"], locale)
    path.write_text(
        yaml.safe_dump(canonical, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def main() -> None:
    scope = _scope_metadata()
    paths = sorted(BANDS.glob("*/*.yaml"))
    for path in paths:
        normalize(path, scope)
    print(f"Normalized {len(paths)} band files to schema version 1")


if __name__ == "__main__":
    main()
