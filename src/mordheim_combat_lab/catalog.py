"""Ruleset-aware loader for executable knowledge packages."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os, sys, yaml

@dataclass(frozen=True, slots=True)
class BandPackage:
    collection: str; ruleset: str; band: dict; profiles: tuple[dict, ...]; equipment_lists: tuple[dict, ...]
    special_rules: tuple[dict, ...]; path: Path

def knowledge_root() -> Path:
    override = os.environ.get("MORDHEIM_COMBAT_LAB_KNOWLEDGE_PATH")
    if override: return Path(override)
    if getattr(sys, "frozen", False): return Path(sys._MEIPASS) / "sources" / "knowledge"
    return Path(__file__).resolve().parents[2] / "sources" / "knowledge"

def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"expected a mapping in {path}")
    return value

@lru_cache(maxsize=None)
def load_collections(root: Path | None = None):
    document = read_yaml((root or knowledge_root()) / "registry/collections.yaml")
    rows = tuple(document.get("collections") or ())
    ids = [str(row.get("id") or "") for row in rows]
    if any(not collection_id for collection_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("collection registry has missing or duplicate IDs")
    return rows

@lru_cache(maxsize=None)
def load_bands(collection: str, root: Path | None = None):
    base = root or knowledge_root(); result = []
    collections = {str(row["id"]): row for row in load_collections(base)}
    if collection not in collections:
        raise ValueError(f"unknown band collection: {collection}")
    allowed_rulesets = set(collections[collection].get("rulesets") or ())
    for path in sorted((base / "bands" / collection).glob("*/band.yaml")):
        directory = path.parent
        band = read_yaml(path)
        ruleset = str(band.get("ruleset") or "")
        if not ruleset:
            raise ValueError(f"band package has no ruleset: {path}")
        if ruleset not in allowed_rulesets:
            raise ValueError(f"collection {collection} does not allow ruleset {ruleset}: {path}")
        result.append(BandPackage(collection, ruleset, band, tuple(read_yaml(directory/"profiles.yaml").get("profiles") or ()), tuple(read_yaml(directory/"equipment-access.yaml").get("equipment_lists") or ()), tuple(read_yaml(directory/"special-rules.yaml").get("rules") or ()), directory))
    return tuple(result)

@lru_cache(maxsize=None)
def load_mechanics(ruleset: str, root: Path | None = None):
    document = read_yaml((root or knowledge_root()) / "catalog/mechanics/close-combat.yaml")
    if document.get("ruleset") != ruleset: raise ValueError(f"catalogue does not describe {ruleset}")
    return document

@lru_cache(maxsize=None)
def load_execution_contract(ruleset: str, root: Path | None = None):
    document = read_yaml((root or knowledge_root()) / "catalog/mechanics/execution.yaml")
    if document.get("ruleset") != ruleset: raise ValueError(f"execution contract does not describe {ruleset}")
    return document

@lru_cache(maxsize=None)
def load_items(ruleset: str, root: Path | None = None):
    base = (root or knowledge_root()) / "catalog/items"
    rows = []
    for path in sorted(base.glob("*.yaml")):
        document = read_yaml(path)
        if document.get("ruleset") != ruleset:
            raise ValueError(f"item catalogue does not describe {ruleset}: {path}")
        rows.extend(document.get("items") or ())
    ids = [str(row.get("id") or "") for row in rows]
    if any(not item_id for item_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("item catalogue has missing or duplicate IDs")
    return tuple(rows)

@lru_cache(maxsize=None)
def load_simulation_mappings(ruleset: str, root: Path | None = None):
    base = root or knowledge_root()
    document = read_yaml(base / "catalog/mechanics/simulation-mappings.yaml")
    if document.get("ruleset") != ruleset: raise ValueError(f"simulation mappings do not describe {ruleset}")
    mechanics = load_mechanics(ruleset, base)
    mechanic_options = {
        str(row["id"]): row.get("engine_option")
        for family in ("weapons","armours","defences","materials","preparations","poisons","skills")
        for row in mechanics.get(family) or ()
    }
    declared = document.get("item_mappings") or ()
    declared_ids = [str(row.get("item_id") or "") for row in declared]
    if any(not item_id for item_id in declared_ids) or len(declared_ids) != len(set(declared_ids)):
        raise ValueError("simulation mappings have missing or duplicate item IDs")
    mappings = {str(row["item_id"]): dict(row) for row in declared}
    for item in load_items(ruleset, base):
        item_id = str(item["id"])
        if item_id in mappings:
            continue
        status = item.get("combat_status") or "out_of_scope"
        mechanic_id = item.get("mechanic_id")
        if status == "implemented":
            engine_option = mechanic_options.get(str(mechanic_id))
            if not mechanic_id or not engine_option:
                raise ValueError(f"implemented item has no executable mechanic: {item_id}")
            mappings[item_id] = {
                "item_id": item_id, "status": "implemented",
                "mechanic_id": mechanic_id, "engine_option": engine_option,
            }
        elif status == "out_of_scope":
            mappings[item_id] = {"item_id": item_id, "status": "out_of_scope"}
        else:
            raise ValueError(f"unknown combat status for item {item_id}: {status}")
    return {**document, "item_mappings": tuple(mappings.values())}

@lru_cache(maxsize=None)
def load_skills(ruleset: str, root: Path | None = None):
    base=(root or knowledge_root()) / "catalog/skills"; rows=[]
    for path in sorted(base.glob("*.yaml")):
        document=read_yaml(path)
        if document.get("ruleset") != ruleset: raise ValueError(f"skill catalogue does not describe {ruleset}: {path}")
        rows.extend(document.get("skills") or ())
    return tuple(rows)

@lru_cache(maxsize=None)
def load_runtime_scope(ruleset: str, root: Path | None = None):
    document=read_yaml((root or knowledge_root())/"registry/runtime-scope.yaml")
    if document.get("ruleset") != ruleset:raise ValueError(f"runtime scope does not describe {ruleset}")
    return document
