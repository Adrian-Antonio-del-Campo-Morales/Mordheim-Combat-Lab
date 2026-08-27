"""Validate the active catalogue and executable contract."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from mordheim_combat_lab.catalog import knowledge_root,load_bands,load_collections,load_items,load_mechanics,load_runtime_scope,load_simulation_mappings,read_yaml
from mordheim_combat_lab.compiler import TRAIT_TYPES,compile_fighter,validate_execution_contract
from mordheim_combat_lab.models import FighterBuild
def validate_mordheim_profiles(bands):
    errors=[];scope=load_runtime_scope("mordheim")
    exclusions={(row.get("band_id"),row.get("profile_id")) for row in scope.get("profile_exclusions") or ()}
    if set(scope.get("supported_combat_traits") or ())!=set(TRAIT_TYPES):errors.append("runtime scope combat traits differ from compiler traits")
    mapped_items={row.get("item_id") for row in load_simulation_mappings("mordheim").get("item_mappings") or ()}
    compiled=excluded=rule_count=0
    for band in bands:
        band_id=band.band.get("id");profile_ids={p.get("id") for p in band.profiles};list_ids={row.get("id") for row in band.equipment_lists};rule_ids={row.get("id") for row in band.special_rules}
        rule_count+=len(band.special_rules)
        for label,rows in (("profiles",band.profiles),("equipment lists",band.equipment_lists),("special rules",band.special_rules)):
            ids=[row.get("id") for row in rows]
            if len(ids)!=len(set(ids)):errors.append(f"{band_id}: duplicate {label}")
        for member in (band.band.get("roster") or {}).get("members") or ():
            if member.get("profile_id") not in profile_ids:errors.append(f"{band_id}: unknown roster profile {member.get('profile_id')}")
        for profile in band.profiles:
            profile_id=profile.get("id");key=(band_id,profile_id)
            missing_lists=set(profile.get("equipment_lists") or ())-list_ids
            if missing_lists:errors.append(f"{band_id}/{profile_id}: unknown equipment lists {sorted(missing_lists)}")
            missing_rules=set(profile.get("rule_ids") or ())-rule_ids
            if missing_rules:errors.append(f"{band_id}/{profile_id}: unknown special rules {sorted(missing_rules)}")
            unknown_traits=set((profile.get("combat_traits") or {}))-set(TRAIT_TYPES)
            if unknown_traits:errors.append(f"{band_id}/{profile_id}: unknown combat traits {sorted(unknown_traits)}")
            if key in exclusions:excluded+=1;continue
            try:compile_fighter(FighterBuild("mordheim",band_id=band_id,profile_id=profile_id))
            except Exception as exc:errors.append(f"{band_id}/{profile_id}: does not compile: {exc}")
            else:compiled+=1
        for equipment in band.equipment_lists:
            for item in equipment.get("items") or ():
                if item.get("item_id") not in mapped_items:errors.append(f"{band_id}: unmapped item {item.get('item_id')}")
        for rule in band.special_rules:
            targets=set((rule.get("applies_to") or {}).get("profile_ids") or ())
            if targets-profile_ids:errors.append(f"{band_id}/{rule.get('id')}: unknown target profiles {sorted(targets-profile_ids)}")
    if compiled+excluded!=316:errors.append(f"expected 316 classified Mordheim profiles, found {compiled} compiled and {excluded} excluded")
    if rule_count!=878:errors.append(f"expected 878 classified Mordheim special rules, found {rule_count}")
    policy=scope.get("special_rule_policy") or {}
    if policy.get("default")!="editorial_out_of_scope" or policy.get("executable_binding")!="profile.combat_traits":errors.append("special-rule runtime classification policy is incomplete")
    return errors,compiled,excluded
def main():
    errors=validate_execution_contract("mordheim");bands=load_bands("mordheim")
    collections={row["id"]:row for row in load_collections()}
    if set(collections)!={"mordheim","trollheim"}:errors.append(f"unexpected collection registry: {sorted(collections)}")
    if set(collections.get("trollheim",{}).get("rulesets") or ())!={"mordheim"}:errors.append("Trollheim collection must use the Mordheim ruleset")
    if len(bands)!=48:errors.append(f"expected 48 Mordheim bands, found {len(bands)}")
    trollheim=load_bands("trollheim")
    if len(trollheim)!=33:errors.append(f"expected 33 Trollheim bands, found {len(trollheim)}")
    ids=[band.band.get("id") for band in bands]
    if len(ids)!=len(set(ids)):errors.append("duplicate band IDs")
    profile_errors,compiled,excluded=validate_mordheim_profiles(bands);errors.extend(profile_errors)
    root=knowledge_root();item_ids=set()
    for path in (root/"catalog/items").glob("*.yaml"):
        item_ids.update(row["id"] for row in read_yaml(path).get("items") or ())
    mechanics=load_mechanics("mordheim")
    mappings=load_simulation_mappings("mordheim").get("item_mappings") or ()
    mapped_ids={row.get("item_id") for row in mappings}
    if mapped_ids!=item_ids:errors.append(f"item mapping coverage differs from catalogue: missing={sorted(item_ids-mapped_ids)}, extra={sorted(mapped_ids-item_ids)}")
    invalid_statuses={row.get("status") for row in mappings}-{"implemented","out_of_scope"}
    if invalid_statuses:errors.append(f"unknown item mapping statuses: {sorted(invalid_statuses)}")
    mechanic_ids={row["id"] for family in ("weapons","armours","defences","materials","preparations","poisons","skills") for row in mechanics[family]}
    for band in trollheim:
        profile_ids={profile["id"] for profile in band.profiles}
        roster_ids={member["profile_id"] for member in band.band["roster"]["members"]}
        summoned_ids={profile["id"] for profile in band.profiles if profile.get("type")=="summoned"}
        if roster_ids!=profile_ids-summoned_ids:errors.append(f"{band.band['id']}: roster/profile mismatch")
        rule_ids={rule["id"] for rule in band.special_rules}
        references=set(band.band.get("rule_ids") or ())
        references.update(rule_id for profile in band.profiles for rule_id in profile.get("rule_ids") or ())
        if not references<=rule_ids:errors.append(f"{band.band['id']}: missing special-rule definitions")
        used_items={item["item_id"] for equipment in band.equipment_lists for item in equipment.get("items") or ()}
        if not used_items<=item_ids:errors.append(f"{band.band['id']}: unknown item IDs {sorted(used_items-item_ids)}")
        used_mechanics={rule["mechanic_id"] for rule in band.special_rules if rule.get("mechanic_id")}
        if not used_mechanics<=mechanic_ids:errors.append(f"{band.band['id']}: unknown mechanic IDs {sorted(used_mechanics-mechanic_ids)}")
        for profile in band.profiles:
            try:
                compile_fighter(FighterBuild(
                    "mordheim", band_id=band.band["id"], profile_id=profile["id"],
                    collection="trollheim"))
            except Exception as exc:
                errors.append(f"{band.band['id']}/{profile['id']}: does not compile under Mordheim rules: {exc}")
    if errors:raise SystemExit("\n".join(f"- {error}" for error in errors))
    trollheim_profiles=sum(len(band.profiles) for band in trollheim)
    print(f"OK: Mordheim ({compiled} compiled, {excluded} excluded), {trollheim_profiles} Trollheim profiles compile under Mordheim rules")
if __name__=="__main__":main()
