"""Normalize all captured Mordheimer warbands into the runtime band schema."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "sources" / "knowledge" / "intake"
BANDS = ROOT / "sources" / "knowledge" / "bands" / "mordheimer"
STATS = ("M", "WS", "BS", "S", "T", "W", "I", "A", "Ld")
ITEM_ALIASES = {
    "double handed weapon": "great_weapon", "long bow": "long_bow",
    "short bow": "short_bow", "morning star": "morning_star",
    "light armour": "light_armour", "heavy armour": "heavy_armour",
    "duelling pistol": "duelling_pistol", "hunting rifle": "hunting_rifle",
    "throwing stars": "throwing_stars", "fighting claws": "fighting_claws",
    "weeping blades": "weeping_blades", "sigmarite warhammer": "sigmarite_hammer",
    "steel whip": "steel_whip", "warplock pistol": "warp_pistol",
}
SKILL_ALIASES = {
    "beastmen chieftain": "chief", "halfling thieves": "thief",
    "bosses": "boss", "beserkers": "berserker",
}


def plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).lower().split())


def slug(value: str, separator: str = "-") -> str:
    return plain(value).replace(" ", separator)


def clean_profile_title(value: str) -> str:
    value = re.sub(r"^\s*\d+\s*(?:[–—�-]\s*\d+\s*)?", "", value).strip()
    return value or "Warrior"


def source(band, section):
    return {"manual": "mordheimer.net", "printed_page": 0, "section": section,
            "url": band["source_url"]}


def section_map(capture):
    return {row["section"]: row["text"] for row in capture.get("section_text", [])}


def parse_cost(text: str) -> int:
    match = re.search(r"(?:cost:\s*)?(\d+)\s+(?:gold crowns?|gc)(?:\s+to\s+(?:hire|buy|recruit))?", text, re.I)
    return int(match.group(1)) if match else 0


def parse_experience(name: str, kind: str, text: str) -> int:
    if kind == "henchman":
        return 0
    tokens = [token for token in plain(name).split() if token not in {"the", "a", "an"}]
    for sentence in re.split(r"(?<=[.])\s+", text):
        normalized = plain(sentence)
        if tokens and not any(token in normalized for token in tokens):
            continue
        match = re.search(r"(?:starts?|start)\s+with\s+(\d+)\s+experience", sentence, re.I)
        if match:
            return int(match.group(1))
    return 0


def item_id(name: str) -> str:
    normalized = plain(name)
    normalized = re.sub(r"\s*\*+$", "", normalized)
    return ITEM_ALIASES.get(normalized, normalized.replace(" ", "_"))


def item_cost(raw: str):
    free_then = re.search(r"1st\s+free\s*/\s*(\d+)", raw, re.I)
    if free_then:
        return int(free_then.group(1))
    dice = re.search(r"(?:\d+\s*\+\s*)?(?:\d+)?D6(?:\s*[x×*]\s*\d+)?", raw, re.I)
    if dice:
        return re.sub(r"\s+", "", dice.group()).replace("×", "x").replace("*", "x")
    match = re.search(r"\d+", raw)
    return int(match.group()) if match else 0


def equipment_lists(capture):
    grouped = {}
    for table in capture.get("tables", []):
        rows, path = table.get("rows", []), table.get("section_path", [])
        if not rows or rows[0] != ["Item", "Cost"]:
            continue
        group = next((part for part in reversed(path[:-1]) if "equipment" in plain(part)), "Equipment list")
        key = slug(group)
        entry = grouped.setdefault(key, {"id": key, "name": group, "items": [],
                                         "source": source(capture, group)})
        for row in rows[1:]:
            if len(row) < 2:
                continue
            raw_cost = row[1]
            parsed_cost = item_cost(raw_cost)
            if parsed_cost == 0 and "free" not in raw_cost.casefold():
                continue
            item = {"item_id": item_id(row[0]), "cost": parsed_cost}
            if not re.fullmatch(r"\s*\d+\s*(?:gc)?\s*", raw_cost, re.I):
                item["notes"] = raw_cost
            if item not in entry["items"]:
                entry["items"].append(item)
    return list(grouped.values())


def skill_access(capture):
    result = {}
    categories = {"combat": "combat", "shooting": "shooting", "academic": "academic",
                  "strength": "strength", "speed": "speed", "special": "special"}
    for table in capture.get("tables", []):
        rows = table.get("rows", [])
        if not rows or not any("skill table" in plain(part) for part in table.get("section_path", [])):
            continue
        headers = [categories.get(plain(value)) for value in rows[0]]
        for row in rows[1:]:
            result[plain(row[0])] = [headers[i] for i, value in enumerate(row[1:], 1)
                                     if i < len(headers) and headers[i] and value.strip()]
    return result


def choose_equipment(name: str, profile_text: str, lists):
    available = {plain(entry["name"]): entry["id"] for entry in lists}
    mentioned = plain(profile_text)
    if any(marker in mentioned for marker in (
        "weapons armour none", "never use weapons", "cannot use weapons",
        "do not need any weapons", "do not use weapons", "may not use weapons",
        "can never use weapons", "can never be given weapons",
    )):
        return []
    matches = [list_id for label, list_id in available.items() if label.replace(" equipment lists", "") in mentioned]
    if matches:
        return matches
    profile_name = plain(name)
    specific = [list_id for label, list_id in available.items()
                if any(word in label for word in profile_name.split())]
    return specific or ([lists[0]["id"]] if lists else [])


def profile_skills(name: str, skills):
    key = plain(name)
    key = SKILL_ALIASES.get(key, key)
    if key in skills:
        return skills[key]
    name_tokens = set(key.rstrip("s").split())
    matches = [(len(name_tokens & set(candidate.rstrip("s").split())), values)
               for candidate, values in skills.items()]
    return max(matches, default=(0, []))[1] if matches and max(matches)[0] else []


def profile_rules(capture, profile_path):
    rules = []
    for row in capture.get("section_text", []):
        path = row.get("section_path", [])
        if len(path) <= len(profile_path) or path[:len(profile_path)] != profile_path:
            continue
        name = row["section"]
        if plain(name) == "special rules":
            text = row.get("text", "").strip()
            # Mordheimer normally groups several named rules in one text block,
            # separated by blank lines (for example "Leader: ...\n\nMagic User: ...").
            # YAML preserves the source paragraph boundary as either one or two
            # newlines, depending on how the page markup was rendered.
            candidates = re.finditer(r"(?:\A|\n)\s*([A-Z][^:\n]{0,47}?):\s*", text)
            # Colons also occur inside wrapped rule prose ("Roll a D6:"). A
            # heading is short, starts in uppercase, and is not a sentence.
            matches = [match for match in candidates if "." not in match.group(1)]
            if matches:
                for index, match in enumerate(matches):
                    rule_name = match.group(1).strip()
                    end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                    effect = text[match.end():end].strip()
                    rules.append({"id": slug(rule_name), "name": rule_name, "effect": effect,
                                  "source": source(capture, f"{' / '.join(profile_path)} / Special Rules / {rule_name}")})
            elif text:
                rules.append({"id": "special-rules", "name": "Special Rules", "effect": text,
                              "source": source(capture, f"{' / '.join(profile_path)} / Special Rules")})
            continue
        rules.append({"id": slug(name), "name": name, "effect": row["text"],
                      "source": source(capture, name)})
    return rules


def normalize(capture):
    texts = section_map(capture)
    lists = equipment_lists(capture)
    skills = skill_access(capture)
    experience_text = texts.get("Starting experience", "")
    profiles, members = [], []
    for table in capture.get("tables", []):
        rows, path = table.get("rows", []), table.get("section_path", [])
        if not rows or rows[0][-9:] != list(STATS) or len(path) < 2:
            continue
        parent = plain(path[0])
        if parent not in {"heroes", "heroines", "henchmen", "henchwomen"}:
            continue
        kind = "hero" if parent in {"heroes", "heroines"} else "henchman"
        name = clean_profile_title(path[-1])
        profile_text = texts.get(path[-1], "")
        animal_name = plain(name)
        if (any(marker in animal_name for marker in (
                "warhound", "beasthound", "monkey", "dire wolf", "giant rat", "rat ogre", "chaos hound"))
                or animal_name in {"bear", "wolf", "hound", "rat"}):
            kind = "animal"
        count = re.match(r"^\s*(\d+)\s*(?:[–—�-]\s*(\d+))?", path[-1])
        minimum, maximum = 0, None
        if count:
            first, second = int(count.group(1)), count.group(2)
            if second is None and first == 1:
                minimum = maximum = 1
            else:
                maximum = int(second or first)
        for row in rows[1:]:
            values = row[-9:]
            if len(values) != 9 or not all(re.match(r"^\d+", value) for value in values):
                continue
            profile_id = slug(name)
            if any(profile["id"] == profile_id for profile in profiles):
                profile_id = f"{profile_id}-{len(profiles) + 1}"
            rules = profile_rules(capture, path)
            cost = parse_cost(profile_text)
            if cost == 0 and profile_text:
                rules.append({"id": "special-recruitment", "name": "Special Recruitment",
                              "effect": profile_text, "source": source(capture, path[-1])})
            profile = {
                "id": profile_id, "name": name, "type": kind,
                "cost": cost,
                "experience": parse_experience(name, kind, experience_text),
                "characteristics": {stat: int(re.match(r"\d+", value).group()) for stat, value in zip(STATS, values)},
                "equipment_lists": choose_equipment(name, profile_text, lists),
                "fixed_equipment": [], "equipment_restrictions": [],
                "skill_access": profile_skills(name, skills),
                "rules": rules, "source": source(capture, path[-1]),
                "source_path": path,
            }
            profiles.append(profile)
            members.append({"profile_id": profile_id, "minimum": minimum, "maximum": maximum})
    choice = texts.get("Choice of warriors", "")
    start = re.search(r"(\d+)\s+gold crowns", choice, re.I)
    maximum = re.search(r"maximum number of (?:warriors|models).*?(\d+)", choice, re.I)
    minimum = re.search(r"minimum of\s+(\d+)\s+models", choice, re.I)
    band_rules = []
    for row in capture.get("section_text", []):
        path = row.get("section_path", [])
        normalized_path = [plain(part) for part in path]
        rule_group = any(any(marker in part for marker in
                         ("special rule", "special skill", "blessing", "mutation", "power"))
                         for part in normalized_path[:-1] or normalized_path)
        if rule_group:
            section = " / ".join(path)
            band_rules.append({"id": slug(section), "name": row["section"], "effect": row["text"],
                               "source": source(capture, section)})
    return {
        "id": capture["id"], "name": capture["name"], "grade": capture["grade"],
        "status": "source-normalized", "source": source(capture, capture["name"]),
        "roster": {"minimum_models": int(minimum.group(1)) if minimum else 3,
                   "maximum_models": int(maximum.group(1)) if maximum else 15,
                   "starting_gold": int(start.group(1)) if start else 500, "members": members},
        "equipment_lists": lists, "profiles": profiles, "band_rules": band_rules,
        "source_sections": capture.get("section_text", []),
    }


def main():
    BANDS.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(INTAKE.glob("*.yaml")):
        capture = yaml.safe_load(path.read_text(encoding="utf-8"))
        target = BANDS / path.name
        rendered = yaml.safe_dump(normalize(capture), allow_unicode=True, sort_keys=False).replace("�", "–")
        target.write_text(rendered, encoding="utf-8")
        count += 1
    scope_path = ROOT / "sources" / "knowledge" / "index" / "warband-scope.yaml"
    scope = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    for warband in scope.get("warbands", []):
        warband["status"] = "source-normalized"
    scope_path.write_text(yaml.safe_dump(scope, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Normalized {count} Mordheimer warbands")


if __name__ == "__main__":
    main()
