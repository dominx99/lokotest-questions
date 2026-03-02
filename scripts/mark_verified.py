"""Mark verified questions in pytania.json based on verification results.

Reads {name}-verification.json, finds all questions with OK status,
and sets verified=true on matching questions in {name}-pytania.json.

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
    v_path = base / f"{name}-verification.json"
    q_path = base / f"{name}-pytania.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found", file=sys.stderr)
        sys.exit(1)
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    v_data = load_json(v_path)
    q_data = load_json(q_path)

    # Collect UUIDs with OK status
    ok_uuids = {
        r["uuid"] for r in v_data["results"] if r["status"] == "OK"
    }

    if not ok_uuids:
        print("Brak pytań OK do oznaczenia jako zweryfikowane.")
        return

    # Mark matching questions as verified
    marked = 0
    for q in q_data["questions"]:
        if q["uuid"] in ok_uuids and not q.get("verified"):
            q["verified"] = True
            marked += 1

    save_json(q_path, q_data)
    print(f"Oznaczono {marked} pytań jako zweryfikowane (z {len(ok_uuids)} OK).")


if __name__ == "__main__":
    main()
