"""Report canonical-review coverage without modifying the knowledge records."""
from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "sources" / "knowledge"


def main() -> None:
    scope = yaml.safe_load((KB / "index" / "warband-scope.yaml").read_text(encoding="utf-8"))
    intake = {p.stem for p in (KB / "intake").glob("*.yaml")}
    records = {
        p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in (KB / "bands" / "mordheimer").glob("*.yaml")
    }
    rows = []
    for band in scope["warbands"]:
        record = records.get(band["id"])
        state = "draft" if record and record.get("status") == "source-structured-draft" else "canonical" if record else "captured" if band["id"] in intake else "missing"
        rows.append(f"| {band['grade']} | {band['name']} | {state} |")
    report = "# Knowledge-base coverage\n\n| Grade | Warband | State |\n|---|---|---|\n" + "\n".join(rows) + "\n"
    (ROOT / "notes" / "knowledge-coverage.md").write_text(report, encoding="utf-8")
    drafts = sum(record.get("status") == "source-structured-draft" for record in records.values())
    print(f"Canonical: {len(records) - drafts}; drafts: {drafts}; captured: {len(intake)}; missing: {len(scope['warbands']) - len(intake)}")


if __name__ == "__main__":
    main()
