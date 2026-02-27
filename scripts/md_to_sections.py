"""Split instruction Markdown into sections by § (paragraph) markers.

Expected input:  instructions/{name}/{name}.md
Expected output: instructions/{name}/{name}-sections.json

Each section has: id, title, chapter, text.
Text before the first § is skipped (title page, table of contents).
Text after the last § is stored as section id="_attachments".
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_sections(md_text: str) -> list[dict]:
    """Parse markdown into sections split on **§ X** markers."""
    lines = md_text.splitlines()

    # Collect all § marker positions
    section_starts: list[tuple[int, str]] = []  # (line_index, section_id)
    for i, line in enumerate(lines):
        m = re.match(r"^\*\*§\s+(\d+\w?)\*\*\s*$", line.strip())
        if m:
            section_starts.append((i, f"§ {m.group(1)}"))

    if not section_starts:
        print("  WARNING: no § markers found", file=sys.stderr)
        return []

    # Track current chapter as we scan
    current_chapter = ""
    sections: list[dict] = []

    for idx, (start_line, section_id) in enumerate(section_starts):
        # Look backwards from this § to find the most recent chapter heading
        for j in range(start_line - 1, -1, -1):
            cm = re.match(r"^\*\*Rozdział\s+\d+[a-z]?\.\*\*\s*$", lines[j].strip())
            if cm:
                # Chapter title is on the next non-empty line
                chapter_line = lines[j].strip().strip("*")
                # Find the chapter subtitle (next bold line)
                for k in range(j + 1, min(j + 5, len(lines))):
                    stripped = lines[k].strip()
                    if stripped.startswith("**") and stripped.endswith("**"):
                        chapter_line += " " + stripped.strip("*")
                        break
                current_chapter = chapter_line.strip()
                break

        # Title: next bold line after the § marker
        title = ""
        title_end = start_line + 1
        for j in range(start_line + 1, min(start_line + 5, len(lines))):
            stripped = lines[j].strip()
            if stripped.startswith("**") and stripped.endswith("**"):
                title = stripped.strip("*").strip()
                title_end = j + 1
                break

        # Text: from after the title to the next § marker (or end of file)
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0]
        else:
            end_line = len(lines)

        text = "\n".join(lines[title_end:end_line]).strip()

        sections.append({
            "id": section_id,
            "title": title,
            "chapter": current_chapter,
            "text": text,
        })

    # Check for attachments after last section
    last_end = section_starts[-1][0]
    # Find end of last section's text — look for attachment markers
    last_section_text = sections[-1]["text"]
    # Split off attachment content if present
    attachment_marker = re.search(
        r"^#{1,4}\s+\*\*Załączniki\*\*",
        last_section_text,
        re.MULTILINE,
    )
    if attachment_marker:
        attachment_text = last_section_text[attachment_marker.start():].strip()
        sections[-1]["text"] = last_section_text[:attachment_marker.start()].strip()
        sections.append({
            "id": "_attachments",
            "title": "Załączniki",
            "chapter": "",
            "text": attachment_text,
        })

    return sections


def process_instruction(instruction_dir: Path) -> None:
    """Process a single instruction directory."""
    name = instruction_dir.name
    md_path = instruction_dir / f"{name}.md"

    if not md_path.exists():
        print(f"  Skipping {name}: no {name}.md found", file=sys.stderr)
        return

    print(f"  {name}/{name}.md -> {name}-sections.json")
    md_text = md_path.read_text(encoding="utf-8")
    sections = parse_sections(md_text)

    output = {
        "instruction": name,
        "sections": sections,
    }

    output_path = instruction_dir / f"{name}-sections.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"    {len(sections)} sections")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split instruction Markdown into sections by § markers.",
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
        if not (instruction_dir / f"{instruction_dir.name}.md").exists():
            continue
        process_instruction(instruction_dir)
        processed += 1

    if processed == 0:
        print("No Markdown files found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone: {processed} instruction(s) processed.")


if __name__ == "__main__":
    main()
