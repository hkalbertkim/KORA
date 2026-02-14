"""Minimal hello_kora runner placeholder."""

from pathlib import Path


def main() -> None:
    graph_path = Path(__file__).with_name("graph.json")
    print(f"TODO: load graph and execute with KORA runtime: {graph_path}")


if __name__ == "__main__":
    main()
