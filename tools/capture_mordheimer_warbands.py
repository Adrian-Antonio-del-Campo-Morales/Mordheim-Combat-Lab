"""Capture structured, source-linked data from the public Mordheimer pages.

This is an intake layer, not a replacement for canonical review. It preserves
tables and headings for every in-scope page so rules can be checked locally.
"""
from __future__ import annotations

import re
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "sources" / "knowledge"
SITE = "https://mordheimer.net"
OVERRIDES = {
    "skaven-clan-eshin": "/docs/warbands/grade-1a-warbands/skaven-eshin",
    "tileans": "/docs/warbands/grade-1b-warbands/tileans",
}


def normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower().replace("the ", ""))


def fetch(path: str) -> BeautifulSoup:
    response = requests.get(SITE + path, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content.decode("utf-8"), "html.parser")


def table_data(table):
    rows = []
    for row in table.select("tr"):
        values = [cell.get_text(" ", strip=True) for cell in row.select("th, td")]
        if values:
            rows.append(values)
    return rows


def labelled_tables(main_tag):
    result, headings = [], {}
    for node in main_tag.find_all(["h2", "h3", "h4", "table"]):
        if node.name != "table":
            level = int(node.name[1])
            headings[level] = node.get_text(" ", strip=True).replace("\u200b", "").strip()
            headings = {key: value for key, value in headings.items() if key <= level}
        else:
            path = [headings[key] for key in sorted(headings)]
            result.append({"section": path[-1] if path else None, "section_path": path, "rows": table_data(node)})
    return result


def section_text(main_tag):
    result, hierarchy = [], {}
    headings = main_tag.find_all(["h2", "h3", "h4"])
    for heading in headings:
        title = heading.get_text(" ", strip=True).replace("\u200b", "").strip()
        level = int(heading.name[1])
        hierarchy[level] = title
        hierarchy = {key: value for key, value in hierarchy.items() if key <= level}
        parts = []
        for sibling in heading.find_next_siblings():
            if sibling.name in {"h2", "h3", "h4"}:
                break
            if sibling.name in {"p", "ul", "ol"}:
                text = sibling.get_text(" ", strip=True)
                if text:
                    parts.append(text)
        if parts:
            result.append({"section": title, "section_path": [hierarchy[key] for key in sorted(hierarchy)], "text": "\n".join(parts)})
    return result


def main() -> None:
    scope_path = KB / "index" / "warband-scope.yaml"
    scope = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    index = fetch("/docs/warbands")
    links = {}
    for anchor in index.select('a[href^="/docs/warbands/"]'):
        label = anchor.get_text(" ", strip=True)
        if label and "#" not in anchor["href"]:
            links.setdefault(normal(label), anchor["href"])

    output = KB / "intake"
    output.mkdir(parents=True, exist_ok=True)
    captured = 0
    for band in scope["warbands"]:
        href = OVERRIDES.get(band["id"], links.get(normal(band["name"])))
        if not href:
            continue
        page = fetch(href)
        main_tag = page.select_one("main") or page
        record = {
            "id": band["id"], "name": band["name"], "grade": band["grade"],
            "source_url": SITE + href, "headings": [h.get_text(" ", strip=True) for h in main_tag.select("h2, h3, h4")],
            "tables": labelled_tables(main_tag),
            "section_text": section_text(main_tag),
        }
        (output / f"{band['id']}.yaml").write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
        captured += 1
    print(f"Captured {captured} source pages in {output}")


if __name__ == "__main__":
    main()
