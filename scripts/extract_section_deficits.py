"""Calculate question deficit per section.

Counts existing questions per section_ref, counts lines in each section file,
computes deficit = max(1, lines // 20) - existing.

Outputs JSON to stdout with sections that need more questions.

Usage:
    uv run python scripts/extract_section_deficits.py Ir-1
    uv run python scripts/extract_section_deficits.py Ir-1 --section 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")


def count_content_lines(filepath: Path) -> int:
    """Count lines excluding YAML frontmatter."""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return len(lines)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return len(lines) - i - 1
    return len(lines)


def parse_frontmatter(filepath: Path) -> dict | None:
    """Parse YAML frontmatter from a section file."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    fm = {}
    for line in lines[1:end]:
        m = re.match(r'^(\w+):\s*"(.+)"$', line.strip())
        if m:
            fm[m.group(1)] = m.group(2)
    return fm


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate question deficit per section.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--section",
        type=str,
        help="Filter by section number (e.g. 2, 12, 31a)",
    )
    args = parser.parse_args()

    base = INSTRUCTIONS_DIR / args.name
    q_path = base / f"{args.name}-pytania.json"
    sections_dir = base / "sections"

    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)
    if not sections_dir.exists():
        print(f"Error: {sections_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Count existing questions per section_ref
    q_data = json.loads(q_path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for q in q_data["questions"]:
        ref = q.get("section_ref") or ""
        normalized = re.sub(r"\s+", "", ref)
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1

    # Process section files
    results = []
    for md_file in sorted(sections_dir.glob("*.md")):
        if md_file.name == "_attachments.md":
            continue

        fm = parse_frontmatter(md_file)
        if not fm or "id" not in fm:
            continue

        section_id = fm["id"]  # e.g. "§ 1"
        normalized_id = re.sub(r"\s+", "", section_id)  # e.g. "§1"

        # Apply section filter
        if args.section:
            if normalized_id != f"§{args.section.strip()}":
                continue

        content_lines = count_content_lines(md_file)
        required = max(1, content_lines // 20)
        existing = counts.get(normalized_id, 0)
        deficit = required - existing

        if deficit <= 0:
            continue

        results.append({
            "section_ref": section_id,
            "section_file": md_file.name,
            "title": fm.get("title", ""),
            "content_lines": content_lines,
            "required": required,
            "existing": existing,
            "deficit": deficit,
            "to_add": min(deficit, 10),
        })

    # Summary to stderr
    total_to_add = sum(r["to_add"] for r in results)
    print(
        f"{len(results)} sections with deficit, {total_to_add} questions to generate",
        file=sys.stderr,
    )

    # Existing questions grouped by section for agent context
    existing_by_section: dict[str, list] = {}
    for q in q_data["questions"]:
        ref = q.get("section_ref") or ""
        normalized = re.sub(r"\s+", "", ref)
        if normalized:
            existing_by_section.setdefault(normalized, []).append(q)

    # Attach existing questions to each result
    for r in results:
        normalized = re.sub(r"\s+", "", r["section_ref"])
        r["existing_questions"] = existing_by_section.get(normalized, [])

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
