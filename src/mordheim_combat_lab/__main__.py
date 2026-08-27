"""Application entry point used by ``python -m`` and packaged executables."""

from .ui.app import main


if __name__ == "__main__":
    raise SystemExit(main())
