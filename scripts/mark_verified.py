"""Mark all questions in pytania.json as verified.

Sets verified=true on all questions in {name}-pytania.json.

Usage:
    uv run python scripts/mark_verified.py Ir-1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <name>")
        sys.exit(1)

    name = sys.argv[1]
    base = INSTRUCTIONS_DIR / name
    q_path = base / f"{name}-pytania.json"

    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    q_data = load_json(q_path)

    # Mark all questions as verified
    marked = 0
    total = len(q_data["questions"])
    for q in q_data["questions"]:
        if not q.get("verified"):
            q["verified"] = True
            marked += 1

    save_json(q_path, q_data)
    print(f"Oznaczono {marked} pytań jako zweryfikowane (z {total} wszystkich).")


if __name__ == "__main__":
    main()
