# KORA

KORA is a Python-first orchestration scaffold for task-graph execution, budgeting, and verification, intended as a minimal open-source foundation for iterative development toward a robust runtime.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 examples/hello_kora/run.py
python3 -m pytest -q
```

## License

Licensed under the Apache License, Version 2.0. See `LICENSE` and `NOTICE`.
