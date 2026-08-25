"""Capture shared English rules needed by the simulator from Mordheimer."""
from __future__ import annotations

from pathlib import Path
import re
import requests
import yaml
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sources" / "knowledge" / "catalog" / "source"
SITE = "https://mordheimer.net"
PAGES = {
    "close-combat-weapons": "/docs/weapons-armour/close-combat",
    "armour": "/docs/weapons-armour/armour",
    "skills": "/docs/campaigns/skills",
    "close-combat-rules": "/docs/rules/close-combat",
    "wounds-and-injuries": "/docs/rules/wounds-and-injuries",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def capture(path: str) -> dict:
    response = requests.get(SITE + path, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
    main = soup.select_one("main") or soup
    records = []
    for heading in main.select("h2, h3"):
        name = heading.get_text(" ", strip=True).replace("\u200b", "").strip()
        parts, seen = [], set()
        for node in heading.next_elements:
            if isinstance(node, Tag) and node.name in {"h2", "h3"}:
                break
            if not isinstance(node, NavigableString) or node.parent.name in {"script", "style"}:
                continue
            text = " ".join(str(node).split())
            if text and text not in seen:
                parts.append(text)
                seen.add(text)
        if parts:
            records.append({"id": slug(name), "name": name, "text": "\n".join(parts)})
    return {"source_url": SITE + path, "records": records}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, path in PAGES.items():
        target = OUTPUT / f"{name}.yaml"
        target.write_text(
            yaml.safe_dump(capture(path), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    print(f"Captured {len(PAGES)} shared Mordheimer catalogues")


if __name__ == "__main__":
    main()
