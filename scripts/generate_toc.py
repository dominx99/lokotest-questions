"""Generate a table of contents from section frontmatters.

Expected input:  instructions/{name}/sections/*.md
Expected output: instructions/{name}/{name}-spis-tresci.md

Reads YAML frontmatter (id, title, chapter) from each section,
groups by chapter, sorts by paragraph number, and writes a TOC file.
"""

import argparse
import re
import sys
from pathlib import Path


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

    # Count content lines (after frontmatter)
    content_lines = len(lines) - end - 1
    fm["content_lines"] = content_lines

    return fm


def section_sort_key(fm: dict) -> tuple:
    """Sort key: extract numeric part from section id like '§ 31a' -> (31, 'a')."""
    section_id = fm.get("id", "")
    m = re.match(r"§\s*(\d+)(\w*)", section_id)
    if m:
        return (int(m.group(1)), m.group(2))
    return (9999, "")


def generate_toc(instruction_dir: Path) -> None:
    """Generate TOC for a single instruction directory."""
    name = instruction_dir.name
    sections_dir = instruction_dir / "sections"

    if not sections_dir.exists():
        print(f"  Skipping {name}: no sections/ directory", file=sys.stderr)
        return

    # Read all section frontmatters
    sections = []
    for md_file in sorted(sections_dir.glob("*.md")):
        if md_file.name == "_attachments.md":
            continue
        fm = parse_frontmatter(md_file)
        if fm and "id" in fm:
            sections.append(fm)

    if not sections:
        print(f"  Skipping {name}: no sections with frontmatter found", file=sys.stderr)
        return

    # Sort by paragraph number
    sections.sort(key=section_sort_key)

    # Group by chapter and build output
    output_lines = []
    current_chapter = None

    for fm in sections:
        chapter = fm.get("chapter", "")
        if chapter != current_chapter:
            current_chapter = chapter
            if output_lines:
                output_lines.append("")
            output_lines.append(f"## {chapter}")

        title = fm.get("title", "")
        section_id = fm.get("id", "")
        output_lines.append(f"- {section_id}. {title}")

    output_lines.append("")

    # Write TOC file
    toc_path = instruction_dir / f"{name}-spis-tresci.md"
    toc_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"  {name}: {len(sections)} sections -> {toc_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate table of contents from section frontmatters.",
    )
    parser.add_argument(
        "--instructions-dir",
        type=Path,
        default=Path("instructions"),
        help="Root instructions directory (default: instructions)",
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Process only a specific instruction (e.g. Ir-1)",
    )
    args = parser.parse_args()

    if args.only:
        dirs = [args.instructions_dir / args.only]
        if not dirs[0].is_dir():
            print(f"Directory not found: {dirs[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        dirs = sorted(d for d in args.instructions_dir.iterdir() if d.is_dir())

    processed = 0
    for instruction_dir in dirs:
        sections_dir = instruction_dir / "sections"
        if not sections_dir.exists():
            continue
        generate_toc(instruction_dir)
        processed += 1

    if processed == 0:
        print("No sections directories found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone: {processed} instruction(s) processed.")


if __name__ == "__main__":
    main()
