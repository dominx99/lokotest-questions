"""Create an empty pytania.json for a new instruction (no existing XLSX).

Usage:
    uv run python scripts/fresh_questions.py Ir-5
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def main() -> None:
    if len(sys.argv) < 2:
        print("Użycie: uv run python scripts/fresh_questions.py <instruction>", file=sys.stderr)
        sys.exit(1)

    name = sys.argv[1]
    path = INSTRUCTIONS_DIR / name / f"{name}-pytania.json"

    if path.exists():
        print(f"{path} already exists, skipping.")
        return

    if not (INSTRUCTIONS_DIR / name).is_dir():
        print(f"Error: directory {INSTRUCTIONS_DIR / name} not found", file=sys.stderr)
        sys.exit(1)

    path.write_text(json.dumps({"instruction": name, "questions": []}, indent=2) + "\n", encoding="utf-8")
    print(f"Created {path}")


if __name__ == "__main__":
    main()
