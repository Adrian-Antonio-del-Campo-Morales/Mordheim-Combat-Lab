"""Validate the installed runtime."""
from .compiler import validate_execution_contract
def main():
    errors=validate_execution_contract()
    if errors:
        for error in errors:print(error)
        return 1
    print("Mordheim Combat Lab knowledge and execution contract are valid.")
    return 0
if __name__=="__main__":raise SystemExit(main())
