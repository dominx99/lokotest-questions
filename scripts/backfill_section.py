"""One-time backfill: add 'section' (int) field to existing pytania.json files.

Extracts the paragraph number from the 'explanation' field.
E.g. explanation="Ir-1 § 12 ust. 1" -> section=12
"""

import json
import re
import sys
from pathlib import Path


def extract_section(explanation: str) -> int | None:
    m = re.search(r"§\s*(\d+)", explanation)
    if m:
        return int(m.group(1))
    return None


def backfill(json_path: Path) -> int:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    updated = 0
    for q in data.get("questions", []):
        section = extract_section(q.get("explanation", ""))
        if q.get("section") != section:
            q["section"] = section
            updated += 1
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return updated


def main() -> None:
    instructions_dir = Path("instructions")
    total = 0
    for json_path in sorted(instructions_dir.glob("*/*-pytania.json")):
        count = backfill(json_path)
        print(f"  {json_path.parent.name}: {count} questions updated")
        total += count
    print(f"\nDone: {total} questions updated.")


if __name__ == "__main__":
    main()
