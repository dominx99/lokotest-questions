"""Prepare add-questions batches: compute deficits, generate agent prompts.

Runs deficit calculation, creates one agent prompt per section that needs
more questions, and outputs a manifest.

Usage:
    uv run python scripts/prepare_add_batches.py Ir-1
    uv run python scripts/prepare_add_batches.py Ir-1 --section 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")
SCRIPTS_DIR = Path(__file__).parent
QUALITY_RULES_PATH = SCRIPTS_DIR / "question_rules.txt"

PROMPT_TEMPLATE = """\
Jesteś generatorem pytań quizowych z instrukcji kolejowej %(instruction)s (PKP).

## Zadanie

1. Przeczytaj plik sekcji: instructions/%(instruction)s/sections/%(section_file)s
2. Wygeneruj %(to_add)d nowych pytań quizowych na podstawie treści sekcji
3. Zapisz wyniki do pliku: %(output_path)s

## Istniejące pytania z tej sekcji (NIE DUPLIKUJ)

%(existing_questions)s

## Wymagania formalne

1. Każde pytanie musi mieć **dokładnie 4 odpowiedzi** (A, B, C, D)
2. Dokładnie **jedna** odpowiedź jest poprawna
3. Każde pytanie musi mieć unikalny UUID (wygeneruj za pomocą pythona: \
`import uuid; str(uuid.uuid4())`)
4. `section_ref` = "%(section_ref)s"

## Zasady jakościowe pytań

%(quality_rules)s

## Format wyjścia — ZAPISZ DO PLIKU

Wygeneruj UUID dla każdego pytania za pomocą Bash: `python3 -c "import uuid; print(uuid.uuid4())"` (wywołaj tyle razy ile potrzebujesz).

Następnie użyj narzędzia **Write** aby zapisać plik `%(output_path)s` z tablicą JSON. Przykład formatu:

```json
[
  {
    "uuid": "wygenerowany-uuid",
    "question": "Treść pytania?",
    "answers": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "correct": "A",
    "explanation": "%(instruction)s § X ust. Y",
    "section_ref": "%(section_ref)s"
  }
]
```

WAŻNE: Do zapisu pliku użyj narzędzia Write (NIE Bash z python3). Plik musi zawierać TYLKO tablicę JSON, bez dodatkowego tekstu.
"""


def load_quality_rules() -> str:
    """Load shared quality rules for prompt templates."""
    return QUALITY_RULES_PATH.read_text(encoding="utf-8").strip()


def count_content_lines(filepath: Path) -> int:
    """Count non-empty lines excluding YAML frontmatter."""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return sum(1 for l in lines if l.strip())
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return sum(1 for l in lines[i + 1:] if l.strip())
    return sum(1 for l in lines if l.strip())


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


def compute_deficits(
    name: str, section_filter: str | None, section_range: str | None = None,
) -> list[dict]:
    """Compute question deficits per section."""
    base = INSTRUCTIONS_DIR / name
    q_path = base / f"{name}-pytania.json"
    sections_dir = base / "sections"

    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)
    if not sections_dir.exists():
        print(f"Error: {sections_dir} not found", file=sys.stderr)
        sys.exit(1)

    q_data = json.loads(q_path.read_text(encoding="utf-8"))

    # Count existing per section
    counts: dict[str, int] = {}
    for q in q_data["questions"]:
        ref = q.get("section_ref") or ""
        normalized = re.sub(r"\s+", "", ref)
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1

    # Existing questions grouped by section
    existing_by_section: dict[str, list] = {}
    for q in q_data["questions"]:
        ref = q.get("section_ref") or ""
        normalized = re.sub(r"\s+", "", ref)
        if normalized:
            existing_by_section.setdefault(normalized, []).append(q)

    results = []
    for md_file in sorted(sections_dir.glob("*.md")):
        if md_file.name == "_attachments.md":
            continue

        fm = parse_frontmatter(md_file)
        if not fm or "id" not in fm:
            continue

        section_id = fm["id"]
        normalized_id = re.sub(r"\s+", "", section_id)

        if section_filter and normalized_id != f"§{section_filter}":
            continue

        if section_range:
            lo, hi = section_range.split("-", 1)
            sec_num = re.sub(r"[^0-9]", "", normalized_id)
            if not sec_num or not (int(lo) <= int(sec_num) <= int(hi)):
                continue

        content_lines = count_content_lines(md_file)
        required = max(1, content_lines // 5)
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
            "to_add": deficit,
            "existing_questions": existing_by_section.get(normalized_id, []),
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare add-questions batches with agent prompts.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--section", type=str, help="Filter by section number (e.g. 5, 12)",
    )
    parser.add_argument(
        "--section-range", type=str,
        help="Filter by section range (e.g. 1-30, 25-85)",
    )
    args = parser.parse_args()

    section = args.section.strip() if args.section else None
    sec_range = args.section_range.strip() if args.section_range else None
    deficits = compute_deficits(args.name, section, sec_range)

    if not deficits:
        print("Brak sekcji wymagających nowych pytań.", file=sys.stderr)
        manifest = {
            "instruction": args.name,
            "total_to_add": 0,
            "batch_count": 0,
            "batches": [],
        }
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    # Print summary table to stderr
    total_to_add = sum(d["to_add"] for d in deficits)
    print(
        f"{'Sekcja':<10} {'Linii':>6} {'Wymag.':>7} {'Istn.':>6}"
        f" {'Deficyt':>8} {'Dodać':>6}",
        file=sys.stderr,
    )
    for d in deficits:
        print(
            f"{d['section_ref']:<10} {d['content_lines']:>6}"
            f" {d['required']:>7} {d['existing']:>6}"
            f" {d['deficit']:>8} {d['to_add']:>6}",
            file=sys.stderr,
        )
    print(f"Razem: {total_to_add} pytań do wygenerowania", file=sys.stderr)

    # Prepare output directory
    tmp_dir = Path(f".tmp/add-questions-{args.name}").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for f in tmp_dir.glob("*.json"):
        f.unlink()
    for f in tmp_dir.glob("*.md"):
        f.unlink()

    # Load shared quality rules
    quality_rules = load_quality_rules()

    # Generate prompts, splitting sections into batches of max 15
    max_per_agent = 15
    batches = []
    for d in deficits:
        ref_clean = re.sub(r"\s+", "", d["section_ref"])
        to_add = d["to_add"]

        # Split into chunks: e.g. 25 → [13, 12], 30 → [15, 15], 14 → [14]
        num_agents = (to_add + max_per_agent - 1) // max_per_agent
        chunks = []
        for i in range(num_agents):
            chunk_size = to_add // num_agents + (1 if i < to_add % num_agents else 0)
            chunks.append(chunk_size)

        for idx, chunk in enumerate(chunks):
            suffix = f"_{idx + 1}" if len(chunks) > 1 else ""
            output_path = tmp_dir / f"{ref_clean}{suffix}.json"
            prompt_path = tmp_dir / f"prompt_{ref_clean}{suffix}.md"

            template = PROMPT_TEMPLATE.replace(
                "%(quality_rules)s", quality_rules,
            )
            prompt = template % {
                "instruction": args.name,
                "section_file": d["section_file"],
                "section_ref": d["section_ref"],
                "to_add": chunk,
                "output_path": str(output_path),
                "existing_questions": json.dumps(
                    d["existing_questions"], ensure_ascii=False, indent=2,
                ),
            }
            prompt_path.write_text(prompt, encoding="utf-8")

            batches.append({
                "section_ref": d["section_ref"],
                "to_add": chunk,
                "output_path": str(output_path),
                "prompt_path": str(prompt_path),
            })

    manifest = {
        "instruction": args.name,
        "total_to_add": total_to_add,
        "batch_count": len(batches),
        "batches": batches,
    }

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
