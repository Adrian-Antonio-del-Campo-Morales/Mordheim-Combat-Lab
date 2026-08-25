"""Materialize source-structured Mordheim drafts into runtime-schema drafts.

This preserves imported provenance while adding the fields required by the
candidate catalogue. Semantics remain marked for rule-mapping review.
"""
from __future__ import annotations
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
BANDS = ROOT / "sources" / "knowledge" / "bands" / "mordheimer"


def number(value: str) -> int:
    match = re.match(r"\d+", str(value))
    return int(match.group()) if match else 0


def main() -> None:
    changed = 0
    for path in BANDS.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("status") != "source-structured-draft":
            continue
        profiles = []
        for row in data.get("derived_profiles", []):
            title = row.get("source_section") or "Warrior"
            profiles.append({
                "id": row["id"], "name": re.sub(r"^\d+\s*[–-]\s*", "", title),
                "type": "henchman", "cost": 0, "experience": 0,
                "characteristics": {key: number(value) for key, value in row["characteristics"].items()},
                "equipment_lists": [], "fixed_equipment": [], "equipment_restrictions": [],
                "skill_access": [], "rules": [],
                "source": {"manual": "mordheimer.net", "printed_page": 0, "section": title},
            })
        data["roster"] = {"minimum_models": 3, "maximum_models": 15, "starting_gold": 500,
                          "members": [{"profile_id": p["id"], "minimum": 0, "maximum": None} for p in profiles]}
        data["equipment_lists"] = []
        data["profiles"] = profiles
        data["band_rules"] = [{"id": "source-rules-pending-mapping", "name": "Source rules pending mapping",
                               "effect": "See source_section_text before engine implementation.",
                               "source": {"manual": "mordheimer.net", "printed_page": 0, "section": "Special Rules"}}]
        data["status"] = "runtime-schema-draft"
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        changed += 1
    print(f"Materialized {changed} runtime-schema drafts")


if __name__ == "__main__":
    main()
