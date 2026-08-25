"""Validate runtime-specific constraints after the shared-schema validation."""
from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
BANDS = ROOT / "sources" / "knowledge" / "bands"
SCOPE = ROOT / "sources" / "knowledge" / "index" / "warband-scope.yaml"
REQUIRED_BAND = {"schema_version", "id", "name", "sources", "roster", "equipment_lists", "profiles"}
REQUIRED_PROFILE = {"id", "name", "type", "cost", "experience", "characteristics", "equipment_lists", "fixed_equipment", "equipment_restrictions", "skill_access", "rules", "source"}
STATS = {"M", "WS", "BS", "S", "T", "W", "I", "A", "Ld"}


def main() -> None:
    failures = []
    paths = sorted((BANDS / "mordheimer").glob("*.yaml"))
    scope = yaml.safe_load(SCOPE.read_text(encoding="utf-8"))
    expected_ids = {row["id"] for row in scope["warbands"]}
    current_ids = {path.stem for path in paths}
    if current_ids != expected_ids:
        failures.append(f"scope mismatch: missing={sorted(expected_ids - current_ids)}, extra={sorted(current_ids - expected_ids)}")
    for path in paths:
        record = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "�" in path.read_text(encoding="utf-8"):
            failures.append(f"{path.name}: contains Unicode replacement characters")
        missing = REQUIRED_BAND - set(record)
        if missing:
            failures.append(f"{path.name}: missing band fields {sorted(missing)}")
            continue
        profile_ids = [profile.get("id") for profile in record["profiles"]]
        if not profile_ids or len(profile_ids) != len(set(profile_ids)):
            failures.append(f"{path.name}: missing or duplicate profile IDs")
        list_ids = [entry.get("id") for entry in record["equipment_lists"]]
        if len(list_ids) != len(set(list_ids)):
            failures.append(f"{path.name}: duplicate equipment-list IDs")
        roster_ids = [row.get("profile_id") for row in record["roster"].get("members", [])]
        if set(roster_ids) != set(profile_ids):
            failures.append(f"{path.name}: roster/profile mismatch")
        for profile in record["profiles"]:
            missing = REQUIRED_PROFILE - set(profile)
            if missing:
                failures.append(f"{path.name}/{profile.get('id', '?')}: missing profile fields {sorted(missing)}")
            elif set(profile["characteristics"]) != STATS:
                failures.append(f"{path.name}/{profile['id']}: incomplete characteristics")
            unknown_lists = set(profile.get("equipment_lists", [])) - set(list_ids)
            if unknown_lists:
                failures.append(f"{path.name}/{profile['id']}: unknown equipment lists {sorted(unknown_lists)}")
            if profile.get("cost") == 0 and not any(
                rule.get("id") == "special-recruitment" for rule in profile.get("rules", [])
            ):
                failures.append(f"{path.name}/{profile['id']}: unexplained zero cost")
            if profile.get("type") == "hero" and not profile.get("skill_access"):
                failures.append(f"{path.name}/{profile['id']}: hero without skill access")
            source_path = profile.get("source_path", [])
            has_special_rules_source = any(
                row.get("section_path", []) == source_path + ["Special Rules"]
                and row.get("text", "").strip()
                for row in record.get("source_sections", [])
            )
            if has_special_rules_source and not profile.get("rules"):
                failures.append(f"{path.name}/{profile['id']}: source special rules were not normalized")
        if any(rule.get("id") == "source-rules-pending-mapping" for rule in record.get("band_rules", [])):
            failures.append(f"{path.name}: obsolete pending-rule marker")
    if failures:
        raise SystemExit("\n".join(failures))
    trollheim_paths = sorted((BANDS / "trollheim").glob("*.yaml"))
    if len(trollheim_paths) != 34:
        raise SystemExit(f"Expected 34 Trollheim bands, found {len(trollheim_paths)}")
    print(f"OK: {len(paths)} Mordheimer and {len(trollheim_paths)} Trollheim runtime bands")


if __name__ == "__main__":
    main()
