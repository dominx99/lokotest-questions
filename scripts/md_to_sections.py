"""Split instruction Markdown into sections by § (paragraph) markers.

Expected input:  instructions/{name}/{name}.md
Expected output: instructions/{name}/sections/*.md

Each section file has YAML frontmatter (id, title, chapter) and text below.
Text before the first § is skipped (title page, table of contents).
Text after the last § is stored as _attachments.md.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


def parse_sections(md_text: str) -> list[dict]:
    """Parse markdown into sections split on **§ X** markers."""
    lines = md_text.splitlines()

    # Collect all § marker positions
    section_starts: list[tuple[int, str]] = []  # (line_index, section_id)
    for i, line in enumerate(lines):
        m = re.match(r"^\*\*§\s+(\d+\w?)\.?\*\*\s*(?:\*\*\[.*?\]\*\*\s*)?$", line.strip())
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
            cm = re.match(r"^\*\*Rozdział\s+(?:\d+[a-z]?\.?|[IVXLCDM]+)\*\*\s*$", lines[j].strip())
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
                # Extract first bold segment only (avoid footnote refs like **[2)]** )
                title_m = re.match(r"^\*\*(.+?)\*\*", stripped)
                title = title_m.group(1).strip() if title_m else stripped.strip("*").strip()
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

    # Check for extra-paragraph content after last section (attachments,
    # appendices, change tables).  We look for the earliest match among
    # several known patterns and split there.
    last_section_text = sections[-1]["text"]
    extra_patterns = [
        # ### **Załączniki** (Ir-1 style heading)
        r"^#{1,4}\s+\*\*Załączniki\*\*",
        # ### **Dodatki do instrukcji** (Ir-1 style appendices)
        r"^#{1,4}\s+\*\*Dodatki\b",
        # **Załącznik nr 1.** (Ir-9 style, standalone bold line)
        r"^\*\*Załącznik\s+nr\s+\d+",
        # **TABELA ZMIAN** / **Tabela zmian**
        r"^\*\*(?:TABELA ZMIAN|Tabela zmian)\*\*",
    ]
    earliest_match = None
    for pat in extra_patterns:
        m = re.search(pat, last_section_text, re.MULTILINE)
        if m and (earliest_match is None or m.start() < earliest_match.start()):
            earliest_match = m

    if earliest_match:
        attachment_text = last_section_text[earliest_match.start():].strip()
        sections[-1]["text"] = last_section_text[:earliest_match.start()].strip()
        sections.append({
            "id": "_attachments",
            "title": "Załączniki",
            "chapter": "",
            "text": attachment_text,
        })

    return sections


def section_filename(section_id: str) -> str:
    """Convert section id to filename, e.g. '§ 12' -> '§12.md', '_attachments' -> '_attachments.md'."""
    if section_id.startswith("§"):
        # Remove space: "§ 12" -> "§12"
        return section_id.replace(" ", "") + ".md"
    return section_id + ".md"


def write_section_file(output_dir: Path, section: dict) -> None:
    """Write a single section as a markdown file with YAML frontmatter."""
    filename = section_filename(section["id"])
    filepath = output_dir / filename

    # Build frontmatter
    lines = [
        "---",
        f'id: "{section["id"]}"',
        f'title: "{section["title"]}"',
        f'chapter: "{section["chapter"]}"',
        "---",
        "",
        section["text"],
        "",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")


def process_instruction(instruction_dir: Path) -> None:
    """Process a single instruction directory."""
    name = instruction_dir.name
    md_path = instruction_dir / f"{name}.md"

    if not md_path.exists():
        print(f"  Skipping {name}: no {name}.md found", file=sys.stderr)
        return

    print(f"  {name}/{name}.md -> sections/")
    md_text = md_path.read_text(encoding="utf-8")
    sections = parse_sections(md_text)

    # Create sections directory (clean if exists)
    output_dir = instruction_dir / "sections"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    for section in sections:
        write_section_file(output_dir, section)

    print(f"    {len(sections)} sections -> {output_dir}/")


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
