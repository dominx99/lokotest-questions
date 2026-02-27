"""Convert instruction XLSX question files to clean JSON.

Expected input:  instructions/{name}/{name}-pytania.xlsx
Expected output: instructions/{name}/{name}-pytania.json

Reads columns A-H (UUID, Question, A-D, Correct, Explanation).
Skips empty columns 9-13 (Image ID, Image URL, etc.).
Extracts section_ref from explanation using regex.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import openpyxl


def extract_section_ref(explanation: str) -> str | None:
    """Extract § reference from explanation text, e.g. 'Ir-1 § 12 ust. 1' -> '§ 12'."""
    m = re.search(r"§\s*(\d+\w?)", explanation)
    if m:
        return f"§ {m.group(1)}"
    return None


def convert_xlsx(xlsx_path: Path, instruction_name: str) -> dict:
    """Convert a single XLSX file to a questions dict."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    questions = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_col=8, values_only=True), start=2):
        uuid, question, ans_a, ans_b, ans_c, ans_d, correct, explanation = row

        # Skip completely empty rows
        if not question:
            continue

        explanation_str = str(explanation) if explanation else ""

        questions.append({
            "uuid": str(uuid).strip() if uuid else "",
            "question": str(question).strip(),
            "answers": {
                "A": str(ans_a).strip() if ans_a else "",
                "B": str(ans_b).strip() if ans_b else "",
                "C": str(ans_c).strip() if ans_c else "",
                "D": str(ans_d).strip() if ans_d else "",
            },
            "correct": str(correct).strip() if correct else "",
            "explanation": explanation_str.strip(),
            "section_ref": extract_section_ref(explanation_str),
        })

    wb.close()

    return {
        "instruction": instruction_name,
        "questions": questions,
    }


def process_instruction(instruction_dir: Path) -> None:
    """Process a single instruction directory."""
    name = instruction_dir.name
    xlsx_path = instruction_dir / f"{name}-pytania.xlsx"

    if not xlsx_path.exists():
        print(f"  Skipping {name}: no {name}-pytania.xlsx found", file=sys.stderr)
        return

    print(f"  {name}/{name}-pytania.xlsx -> {name}-pytania.json")
    result = convert_xlsx(xlsx_path, name)

    output_path = instruction_dir / f"{name}-pytania.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"    {len(result['questions'])} questions")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert instruction XLSX question files to JSON.",
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
        if not (instruction_dir / f"{instruction_dir.name}-pytania.xlsx").exists():
            continue
        process_instruction(instruction_dir)
        processed += 1

    if processed == 0:
        print("No XLSX files found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone: {processed} instruction(s) processed.")


if __name__ == "__main__":
    main()
