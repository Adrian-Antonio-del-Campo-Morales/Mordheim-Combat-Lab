"""Promote source captures to source-linked knowledge drafts.

The resulting files retain all extracted tables and section labels.  They are
explicitly drafts until their rules have been semantically reviewed.
"""
from __future__ import annotations

from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "sources" / "knowledge"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def derived_profiles(tables):
    profiles = []
    stats = ["M", "WS", "BS", "S", "T", "W", "I", "A", "Ld"]
    for table in tables:
        rows = table["rows"]
        if not rows or rows[0][-9:] != stats:
            continue
        for row in rows[1:]:
            values = row[-9:]
            if len(values) != 9 or not all(re.match(r"^\d+(?:\(\d+\))?$", value) for value in values):
                continue
            profiles.append({"id": slug(table.get("section") or "profile"), "source_section": table.get("section"), "characteristics": dict(zip(stats, values))})
    return profiles


def derived_equipment(tables):
    result = []
    for table in tables:
        rows = table["rows"]
        if rows and rows[0] == ["Item", "Cost"]:
            result.append({"source_section": table.get("section"), "items": [{"name": row[0], "cost": row[1]} for row in rows[1:] if len(row) == 2]})
    return result


def main() -> None:
    created = 0
    for intake_path in sorted((KB / "intake").glob("*.yaml")):
        target = KB / "bands" / "mordheimer" / intake_path.name
        if target.exists() and yaml.safe_load(target.read_text(encoding="utf-8")).get("status") != "source-structured-draft":
            continue
        intake = yaml.safe_load(intake_path.read_text(encoding="utf-8"))
        draft = {
            "id": intake["id"], "name": intake["name"], "grade": intake["grade"],
            "status": "source-structured-draft",
            "source": {"url": intake["source_url"], "accessed": "2026-08-24"},
            "sections": intake["headings"], "tables": intake["tables"],
            "source_section_text": intake.get("section_text", []),
            "derived_profiles": derived_profiles(intake["tables"]),
            "derived_equipment": derived_equipment(intake["tables"]),
        }
        target.write_text(yaml.safe_dump(draft, allow_unicode=True, sort_keys=False), encoding="utf-8")
        created += 1
    print(f"Created or refreshed {created} draft band records")


if __name__ == "__main__":
    main()
