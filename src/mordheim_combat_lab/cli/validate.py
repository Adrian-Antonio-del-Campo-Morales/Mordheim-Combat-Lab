"""Command-line validation for the active one-against-one runtime."""

from ..core.compiler import validate_execution_contract


def main() -> int:
    errors = validate_execution_contract()
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Mordheim Combat Lab knowledge and execution contract are valid.")
    return 0
