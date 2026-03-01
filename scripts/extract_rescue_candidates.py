"""Extract DELETE questions from verification as rescue candidates.

Reads verification.json and pytania.json, filters DELETE entries
(optionally by section_ref), outputs JSON with full question data
and delete problems.

Usage:
    uv run python scripts/extract_rescue_candidates.py Ir-1
    uv run python scripts/extract_rescue_candidates.py Ir-1 --section 2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract DELETE questions as rescue candidates.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--section",
        type=str,
        help="Filter by section number (e.g. 2, 12, 31a)",
    )
    args = parser.parse_args()

    base = INSTRUCTIONS_DIR / args.name
    v_path = base / f"{args.name}-verification.json"
    q_path = base / f"{args.name}-pytania.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found", file=sys.stderr)
        sys.exit(1)
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    v_data = json.loads(v_path.read_text(encoding="utf-8"))
    q_data = json.loads(q_path.read_text(encoding="utf-8"))

    # Build question lookup
    q_lookup = {q["uuid"]: q for q in q_data["questions"]}

    # Collect DELETE entries with problems
    delete_entries = {
        r["uuid"]: r.get("problems", [])
        for r in v_data["results"]
        if r["status"] == "DELETE"
    }

    # Build section filter pattern
    section_filter = None
    if args.section:
        # Normalize: "2" -> matches "§ 2", "§2", etc.
        section_filter = args.section.strip()

    def section_matches(ref: str) -> bool:
        if section_filter is None:
            return True
        normalized = re.sub(r"\s+", "", ref or "")
        return normalized == f"§{section_filter}"

    # Filter and build candidates
    candidates = []
    for uuid, problems in delete_entries.items():
        q = q_lookup.get(uuid)
        if not q:
            continue
        if not section_matches(q.get("section_ref", "")):
            continue
        candidates.append({
            "uuid": uuid,
            "question": q.get("question"),
            "answers": q.get("answers"),
            "correct": q.get("correct"),
            "explanation": q.get("explanation"),
            "section_ref": q.get("section_ref"),
            "delete_problems": problems,
        })

    # Output summary to stderr, data to stdout
    total_delete = len(delete_entries)
    filtered = len(candidates)
    if args.section:
        print(
            f"DELETE: {total_delete} total, {filtered} matching § {section_filter}",
            file=sys.stderr,
        )
    else:
        print(f"DELETE: {total_delete} candidates", file=sys.stderr)

    print(json.dumps(candidates, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
