"""Convert instruction JSON question files back to XLSX.

Expected input:  instructions/{name}/{name}-pytania.json
Expected output: instructions/{name}/{name}-pytania.xlsx

Writes columns A-I (UUID, Question, A-D, Correct, Explanation, Section).
"""

import argparse
import json
import sys
from pathlib import Path

import openpyxl


HEADERS = ["UUID", "Question", "A", "B", "C", "D", "Correct", "Explanation", "Section"]


def convert_json(json_path: Path, xlsx_path: Path) -> int:
    """Convert a single JSON file to XLSX. Returns question count."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])

    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(HEADERS)

    for q in questions:
        answers = q.get("answers", {})
        ws.append([
            q.get("uuid", ""),
            q.get("question", ""),
            answers.get("A", ""),
            answers.get("B", ""),
            answers.get("C", ""),
            answers.get("D", ""),
            q.get("correct", ""),
            q.get("explanation", ""),
            q.get("section"),
        ])

    wb.save(xlsx_path)
    return len(questions)


def process_instruction(instruction_dir: Path) -> None:
    """Process a single instruction directory."""
    name = instruction_dir.name
    json_path = instruction_dir / f"{name}-pytania.json"

    if not json_path.exists():
        print(f"  Skipping {name}: no {name}-pytania.json found", file=sys.stderr)
        return

    xlsx_path = instruction_dir / f"{name}-pytania.xlsx"
    print(f"  {name}/{name}-pytania.json -> {name}-pytania.xlsx")
    count = convert_json(json_path, xlsx_path)
    print(f"    {count} questions")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert instruction JSON question files to XLSX.",
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
        if not (instruction_dir / f"{instruction_dir.name}-pytania.json").exists():
            continue
        process_instruction(instruction_dir)
        processed += 1

    if processed == 0:
        print("No JSON files found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone: {processed} instruction(s) processed.")


if __name__ == "__main__":
    main()
