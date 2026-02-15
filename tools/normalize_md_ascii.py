#!/usr/bin/env python3
"""Normalize selected Markdown files to ASCII hyphens."""

from __future__ import annotations

from pathlib import Path

REPLACEMENTS = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u2212": "-",  # minus sign
}

CURLY_QUOTES = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
}


def target_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []

    readme = repo_root / "README.md"
    if readme.exists():
        files.append(readme)

    contributing = repo_root / "CONTRIBUTING.md"
    if contributing.exists():
        files.append(contributing)

    docs_dir = repo_root / "docs"
    if docs_dir.exists():
        files.extend(sorted(p for p in docs_dir.rglob("*.md") if p.is_file()))

    # Preserve deterministic output order and avoid duplicates.
    seen: set[Path] = set()
    ordered: list[Path] = []
    for file in files:
        if file not in seen:
            seen.add(file)
            ordered.append(file)
    return ordered


def normalize_file(path: Path) -> tuple[dict[str, int], dict[str, int], bool]:
    original = path.read_text(encoding="utf-8")
    updated = original

    replacement_counts = {char: 0 for char in REPLACEMENTS}
    for source, target in REPLACEMENTS.items():
        replacement_counts[source] = updated.count(source)
        if replacement_counts[source]:
            updated = updated.replace(source, target)

    curly_counts = {char: updated.count(char) for char in CURLY_QUOTES}

    changed = updated != original
    if changed:
        path.write_text(updated, encoding="utf-8")

    return replacement_counts, curly_counts, changed


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    files = target_files(repo_root)

    total_replacements = {char: 0 for char in REPLACEMENTS}
    total_curly = {char: 0 for char in CURLY_QUOTES}
    changed_files = 0

    for file in files:
        replacement_counts, curly_counts, changed = normalize_file(file)
        if changed or any(count > 0 for count in replacement_counts.values()):
            changed_files += 1 if changed else 0
            print(
                f"{file.relative_to(repo_root)}: "
                f"em_dash={replacement_counts['\u2014']}, "
                f"en_dash={replacement_counts['\u2013']}, "
                f"minus_sign={replacement_counts['\u2212']}"
            )

        for char in REPLACEMENTS:
            total_replacements[char] += replacement_counts[char]
        for char in CURLY_QUOTES:
            total_curly[char] += curly_counts[char]

    print(
        "TOTAL_REPLACEMENTS: "
        f"em_dash={total_replacements['\u2014']}, "
        f"en_dash={total_replacements['\u2013']}, "
        f"minus_sign={total_replacements['\u2212']}"
    )
    print(f"FILES_CHANGED: {changed_files}")

    if any(total_curly.values()):
        print(
            "CURLY_QUOTES_FOUND: "
            f"left_double={total_curly['\u201c']}, "
            f"right_double={total_curly['\u201d']}, "
            f"left_single={total_curly['\u2018']}, "
            f"right_single={total_curly['\u2019']}"
        )


if __name__ == "__main__":
    main()
