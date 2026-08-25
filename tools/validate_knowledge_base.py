"""Validate the materialized, collection-independent knowledge contract."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "sources" / "knowledge"
BAND_KEYS = {
    "schema_version", "id", "canonical_family", "name", "name_i18n", "original_locale",
    "categories", "collections", "grade", "setting", "publication", "status",
    "sources", "roster", "equipment_lists", "profiles", "band_rules",
    "source_sections",
}
CATEGORIES = {"core", "1a", "1b", "1c", "trollheim"}
COLLECTIONS = {"mordheimer", "trollheim"}
STATS = {"M", "WS", "BS", "S", "T", "W", "I", "A", "Ld"}


def _load(path: Path, errors: list[str]) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Invalid YAML in {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"Expected mapping in {path.relative_to(ROOT)}")
        return {}
    return value


def _translation(value, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or set(value) != {"en", "es"}:
        errors.append(f"Invalid bilingual shape: {label}")
        return
    if all(not value.get(locale) for locale in ("en", "es")):
        errors.append(f"Translation has no original text: {label}")


def _source(value, label: str, errors: list[str]) -> None:
    required = {"manual", "printed_page", "section"}
    if not isinstance(value, dict) or not required <= set(value):
        errors.append(f"Invalid source: {label}")


def _rule(rule: dict, label: str, errors: list[str]) -> None:
    required = {"id", "name", "name_i18n", "effect", "effect_i18n", "source"}
    if not required <= set(rule):
        errors.append(f"Incomplete rule: {label}")
        return
    _translation(rule["name_i18n"], f"{label}.name", errors)
    _translation(rule["effect_i18n"], f"{label}.effect", errors)
    _source(rule["source"], label, errors)


def validate_band(path: Path, ids: set[str], errors: list[str]) -> int:
    band = _load(path, errors)
    if set(band) != BAND_KEYS:
        errors.append(
            f"Non-canonical top-level structure in {path.name}: "
            f"missing={sorted(BAND_KEYS - set(band))}, extra={sorted(set(band) - BAND_KEYS)}"
        )
        return 0
    band_id = str(band["id"])
    if band_id in ids:
        errors.append(f"Duplicate band ID: {band_id}")
    ids.add(band_id)
    if band["schema_version"] != 1:
        errors.append(f"Unsupported schema in {path.name}")
    if not set(band["categories"]) <= CATEGORIES or not band["categories"]:
        errors.append(f"Invalid categories in {path.name}: {band['categories']}")
    if not set(band["collections"]) <= COLLECTIONS or not band["collections"]:
        errors.append(f"Invalid collections in {path.name}: {band['collections']}")
    _translation(band["name_i18n"], f"{band_id}.name", errors)
    for index, source in enumerate(band["sources"]):
        _source(source, f"{band_id}.sources[{index}]", errors)

    equipment_ids = set()
    for equipment in band["equipment_lists"]:
        required = {"id", "name", "name_i18n", "items", "source"}
        if not required <= set(equipment):
            errors.append(f"Incomplete equipment list in {band_id}: {equipment.get('id')}")
            continue
        equipment_ids.add(equipment["id"])
        _translation(equipment["name_i18n"], f"{band_id}.{equipment['id']}.name", errors)
        _source(equipment["source"], f"{band_id}.{equipment['id']}", errors)

    profiles = band["profiles"]
    profile_ids = {profile.get("id") for profile in profiles}
    if None in profile_ids or len(profile_ids) != len(profiles):
        errors.append(f"Missing or duplicate profile ID in {band_id}")
    for member in band["roster"].get("members", []):
        if member.get("profile_id") not in profile_ids:
            errors.append(f"Unknown roster profile in {band_id}: {member.get('profile_id')}")
    for profile in profiles:
        label = f"{band_id}.{profile.get('id')}"
        required = {"id", "name", "name_i18n", "type", "cost", "experience", "characteristics", "equipment_lists", "skill_access", "rules", "source"}
        if not required <= set(profile):
            errors.append(f"Incomplete profile: {label}")
            continue
        _translation(profile["name_i18n"], f"{label}.name", errors)
        _source(profile["source"], label, errors)
        if set(profile["characteristics"]) != STATS:
            errors.append(f"Incomplete characteristics: {label}")
        for equipment_id in profile["equipment_lists"]:
            if equipment_id not in equipment_ids:
                errors.append(f"Unknown equipment list in {label}: {equipment_id}")
        for rule in profile["rules"]:
            _rule(rule, f"{label}.{rule.get('id')}", errors)
    for rule in band["band_rules"]:
        _rule(rule, f"{band_id}.{rule.get('id')}", errors)
    return len(profiles)


def main() -> None:
    errors: list[str] = []
    ids: set[str] = set()
    paths = sorted((KB / "bands").glob("*/*.yaml"))
    profiles = sum(validate_band(path, ids, errors) for path in paths)
    counts = {
        collection: len(list((KB / "bands" / collection).glob("*.yaml")))
        for collection in COLLECTIONS
    }
    if counts != {"mordheimer": 49, "trollheim": 34}:
        errors.append(f"Unexpected collection counts: {counts}")
    if profiles != 540:
        errors.append(f"Profile count is {profiles}; expected 540")
    if errors:
        raise SystemExit("\n".join(f"- {error}" for error in errors))
    print(f"OK: {len(paths)} bands and {profiles} profiles share schema version 1")


if __name__ == "__main__":
    main()
