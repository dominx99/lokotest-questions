"""Convert PDF files to clean Markdown optimized for LLM consumption.

Expected structure:
    instructions/
    ├── Ir-1/
    │   ├── Ir-1.pdf    (input)
    │   └── Ir-1.md     (generated)
    └── Ie-1/
        ├── Ie-1.pdf
        └── Ie-1.md
"""

import argparse
import re
import sys
from pathlib import Path

import pymupdf4llm


def clean_markdown(text: str) -> str:
    """Remove PDF artifacts: page numbers, repeated headers, footers.
    Rejoin lines broken mid-sentence by PDF layout."""
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # Skip standalone page numbers
        if re.match(r"^\d{1,3}$", stripped):
            continue

        # Skip repeated PKP header
        if stripped == "PKP POLSKIE LINIE KOLEJOWE S.A.":
            continue

        # Skip table-of-contents lines (dots followed by page number)
        if re.match(r".*\.{4,}\s*\d+\s*$", stripped):
            continue

        cleaned.append(line)

    text = "\n".join(cleaned)

    # Rejoin lines broken mid-sentence by PDF layout.
    text = re.sub(
        r"([a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ0-9,;:)\-–—„])\n\n(?=[a-ząćęłńóśźż])",
        r"\1 ",
        text,
    )

    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


def convert_pdf(pdf_path: Path) -> None:
    """Convert a single PDF to cleaned Markdown next to the source PDF."""
    output_path = pdf_path.with_suffix(".md")
    print(f"  {pdf_path.parent.name}/{pdf_path.name} -> {output_path.name}")

    md_text = pymupdf4llm.to_markdown(str(pdf_path))
    md_text = clean_markdown(md_text)

    output_path.write_text(md_text, encoding="utf-8")
    print(f"    {len(md_text):,} chars")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDFs to clean Markdown for LLM quiz generation.",
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
        help="Convert only a specific instruction (e.g. Ir-1)",
    )
    args = parser.parse_args()

    if args.only:
        dirs = [args.instructions_dir / args.only]
        if not dirs[0].is_dir():
            print(f"Directory not found: {dirs[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        dirs = sorted(
            d for d in args.instructions_dir.iterdir() if d.is_dir()
        )

    converted = 0
    for instruction_dir in dirs:
        pdfs = list(instruction_dir.glob("*.pdf"))
        if not pdfs:
            continue
        for pdf_path in pdfs:
            convert_pdf(pdf_path)
            converted += 1

    if converted == 0:
        print("No PDF files found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone: {converted} file(s) converted.")


if __name__ == "__main__":
    main()
