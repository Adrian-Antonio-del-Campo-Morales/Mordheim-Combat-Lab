"""Comandos de desarrollo y aplicación; las importaciones pesadas son locales."""
from argparse import ArgumentParser
from dataclasses import asdict
from pathlib import Path
import json
import os
import time


def validate_command(args) -> int:
    from mordheim_combat_lab.construction.compiler import compile_fighter
    from mordheim_combat_lab.construction.contracts import validate_execution_contract
    from mordheim_combat_lab.domain.models import FighterBuild
    from mordheim_combat_lab.knowledge.loader import load_bands
    from mordheim_combat_lab.verification.structural import audit_phase_verification

    knowledge = Path(args.knowledge).resolve() if args.knowledge else None
    specs = Path(args.specs).resolve() if args.specs else None
    errors = list(validate_execution_contract("mordheim", knowledge))
    report = audit_phase_verification("mordheim", knowledge, specs)
    errors.extend(report.errors)
    compiled = 0
    for collection in ("mordheim", "trollheim"):
        for band in load_bands(collection, knowledge):
            for profile in band.profiles:
                try:
                    compile_fighter(FighterBuild(
                        "mordheim", collection=collection,
                        band_id=str(band.band["id"]), profile_id=str(profile["id"]),
                    ), knowledge)
                except ValueError as error:
                    # Scope exclusions and mandatory selectable grants are valid
                    # classifications; every other compilation failure is structural.
                    message = str(error).casefold()
                    if not any(expected in message for expected in (
                        "outside the duel runtime", "at least one mutation",
                        "exactly one or two mutations", "requires one or two mutations",
                        "require at least one blessing",
                    )):
                        errors.append(f"{collection}/{band.band['id']}/{profile['id']}: {error}")
                else:
                    compiled += 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"structural_complete=True; {compiled} profiles compile with their default construction")
    print("Semantic status is separate: use `python -m mordheim_combat_lab verify --require-complete`.")
    return 0


def verify_command(args) -> int:
    from mordheim_combat_lab.knowledge.loader import knowledge_root
    from mordheim_combat_lab.verification.audit import verify_semantics
    from mordheim_combat_lab.verification.inventory import inventory
    from mordheim_combat_lab.verification.structural import audit_phase_verification

    knowledge = Path(args.knowledge).resolve() if args.knowledge else knowledge_root()
    specs = Path(args.specs).resolve() if args.specs else None
    if args.inventory:
        print(json.dumps([asdict(item) for item in inventory(knowledge)], ensure_ascii=True, indent=2))
        return 0
    structural = audit_phase_verification("mordheim", knowledge, specs)
    semantic = verify_semantics(knowledge, specs)
    payload = {"structural_complete": structural.structural_complete,
               "structural_errors": structural.errors,
               "semantic_complete": semantic.semantic_complete, **asdict(semantic)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(f"structural_complete={structural.structural_complete}")
        print(f"semantic_complete={semantic.semantic_complete}")
        print(f"{len(semantic.verified)}/{len(semantic.obligations)} obligations verified; "
              f"{len(semantic.pending)} pending; "
              f"{sum(len(item.passed_cases) for item in semantic.fixtures)} passed cases; "
              f"{sum(len(item.killed_mutations) for item in semantic.fixtures)} detected mutations")
        for error in (*structural.errors, *semantic.errors):
            print(f"FAIL: {error}")
        if semantic.pending:
            print("PENDING: use --json for the effect-by-effect backlog.")
    return int(bool(structural.errors or semantic.errors or
                    args.require_complete and not semantic.semantic_complete))


def benchmark_command(args) -> int:
    from mordheim_combat_lab.combat.vectorized import simulate_duel
    from mordheim_combat_lab.construction.compiler import compile_fighter
    from mordheim_combat_lab.domain.models import Characteristics, DuelRequest, FighterBuild

    stats = Characteristics(4, 4, 4, 2, 4, 2)
    first = compile_fighter(FighterBuild("mordheim", stats, main_weapon_id="weapon.sword",
                            off_hand_id="weapon.dagger", armour_id="armour.light-armour",
                            skill_ids=("skill.mighty-blow",)))
    second = compile_fighter(FighterBuild("mordheim", stats, main_weapon_id="weapon.axe",
                             off_hand_id="defence.shield", armour_id="armour.heavy-armour"))
    started = time.perf_counter()
    result = simulate_duel(DuelRequest(first, second, args.simulations, seed=args.seed))
    elapsed = time.perf_counter() - started
    print(f"{args.simulations / elapsed:,.0f} simulations/s; {elapsed:.3f}s; {result}")
    return 0


def ui_command(_args) -> int:
    from mordheim_combat_lab.ui.app import main
    return int(main() or 0)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="mordheim-combat-lab")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("ui", help="abrir la interfaz gráfica").set_defaults(handler=ui_command)
    validation = commands.add_parser("validate", help="validar KB y conexiones estructurales")
    validation.add_argument("--knowledge")
    validation.add_argument("--specs")
    validation.set_defaults(handler=validate_command)
    verification = commands.add_parser("verify", help="ejecutar especificaciones semánticas")
    verification.add_argument("--knowledge")
    verification.add_argument("--specs")
    verification.add_argument("--inventory", action="store_true")
    verification.add_argument("--json", action="store_true")
    verification.add_argument("--require-complete", action="store_true")
    verification.set_defaults(handler=verify_command)
    benchmark = commands.add_parser("benchmark", help="medir el motor vectorizado")
    benchmark.add_argument("-n", "--simulations", type=int, default=500_000)
    benchmark.add_argument("--seed", type=int, default=2026)
    benchmark.set_defaults(handler=benchmark_command)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        return ui_command(args)
    if getattr(args, "inventory", False) and getattr(args, "require_complete", False):
        parser.error("--inventory and --require-complete cannot be combined")
    return args.handler(args)
