"""Module entrypoint for `python -m kora`."""

from __future__ import annotations

from kora.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
