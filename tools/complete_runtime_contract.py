"""Fill non-semantic runtime-schema defaults without replacing source facts."""
from __future__ import annotations
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
BANDS = ROOT / "sources" / "knowledge" / "bands" / "mordheimer"


def title(value: str) -> str:
    return re.sub(r"[-_]", " ", value).title()


def main() -> None:
    changed = 0
    for path in BANDS.glob("*.yaml"):
        band = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "roster" not in band or "profiles" not in band:
            continue
        band.setdefault("equipment_lists", [])
        for equipment_list in band["equipment_lists"]:
            for item in equipment_list.get("items", []):
                if "item_id" not in item and "id" in item:
                    item["item_id"] = item.pop("id")
        for profile in band["profiles"]:
            profile.setdefault("name", title(str(profile.get("id", "Warrior"))))
            legacy_list = profile.pop("equipment_list", None)
            profile.setdefault("equipment_lists", [legacy_list] if legacy_list and legacy_list != "none" else [])
            profile.setdefault("fixed_equipment", [])
            profile.setdefault("equipment_restrictions", [])
            profile.setdefault("skill_access", [])
            profile.setdefault("rules", [])
            profile.setdefault("source", dict(band.get("source") or {}))
        path.write_text(yaml.safe_dump(band, allow_unicode=True, sort_keys=False), encoding="utf-8")
        changed += 1
    print(f"Completed runtime contract for {changed} records")


if __name__ == "__main__":
    main()
