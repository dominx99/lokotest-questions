"""Remove questions by UUID from an instruction's pytania.json file.

Usage: python scripts/remove_questions.py <instruction> <uuid> [<uuid> ...]
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Remove questions by UUID")
    parser.add_argument("instruction", help="Instruction name (e.g. Ir-1)")
    parser.add_argument("uuids", nargs="+", help="UUIDs of questions to remove")
    args = parser.parse_args()

    path = Path(f"instructions/{args.instruction}/{args.instruction}-pytania.json")
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    before = len(data["questions"])
    uuids_to_remove = set(args.uuids)

    found = {q["uuid"] for q in data["questions"]} & uuids_to_remove
    missing = uuids_to_remove - found

    if missing:
        print(f"Warning: UUIDs not found: {', '.join(missing)}", file=sys.stderr)

    data["questions"] = [q for q in data["questions"] if q["uuid"] not in uuids_to_remove]
    after = len(data["questions"])

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Removed {before - after} questions ({before} → {after})")


if __name__ == "__main__":
    main()
