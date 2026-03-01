"""Prepare rescue batches: extract DELETE candidates, group, generate agent prompts.

Creates batch input files and prompt files in /tmp/rescue-{name}/,
outputs a JSON manifest to stdout.

Usage:
    uv run python scripts/prepare_rescue_batches.py Ir-1
    uv run python scripts/prepare_rescue_batches.py Ir-1 --section 5
    uv run python scripts/prepare_rescue_batches.py Ir-1 --batch-size 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTIONS_DIR = Path("instructions")
BATCH_SIZE = 8

PROMPT_TEMPLATE = """\
Jesteś weryfikatorem pytań quizowych z instrukcji kolejowej %(instruction)s (PKP).

## Kontekst

Poniższe pytania zostały oznaczone jako DELETE podczas weryfikacji per-paragrafowej, \
ponieważ nie znaleziono dla nich pokrycia w przypisanej sekcji. Twoim zadaniem jest \
sprawdzić, czy pytanie ma pokrycie W INNEJ sekcji instrukcji.

## Spis treści instrukcji

%(toc_content)s

## Pytania do rescue

%(questions_json)s

Dla każdego pytania jest podane:
- Pełne pytanie (question, answers, correct, explanation, section_ref)
- `delete_problems` — powody oznaczenia DELETE

## Procedura dla KAŻDEGO pytania

1. Przeczytaj treść pytania i powody DELETE
2. Na podstawie spisu treści wytypuj 1-3 sekcje, które mogą zawierać odpowiedź
3. Użyj Read tool aby przeczytać te sekcje: `instructions/%(instruction)s/sections/§X.md`
4. Zdecyduj:

   **RESCUED** — pytanie ma pokrycie w innej sekcji:
   - Podaj `section_ref` prawidłowej sekcji (np. `§ 42`)
   - Opcjonalnie popraw `question`, `answers`, `correct`, `explanation` \
jeśli trzeba je dostosować do nowej sekcji

   **DELETE** — potwierdzony DELETE, pytanie nie ma pokrycia nigdzie w instrukcji

## Format wyników — ZAPISZ DO PLIKU

Po weryfikacji, użyj narzędzia Write aby zapisać wyniki jako JSON do pliku \
%(output_path)s:

```json
[
  {
    "uuid": "...",
    "status": "RESCUED|DELETE",
    "problems": ["opis co znaleziono lub potwierdzenie braku pokrycia"],
    "changes": {
      "section_ref": "§ X",
      "question": "nowa treść (tylko jeśli zmieniona)",
      "answers": {"A": "..."},
      "correct": "B",
      "explanation": "%(instruction)s § X ust. Y"
    }
  }
]
```

Zasady:
- `status`: RESCUED (znaleziono pokrycie w innej sekcji) lub DELETE (potwierdzony brak pokrycia)
- `changes`: **WYMAGANE** dla RESCUED — MUSI zawierać przynajmniej `section_ref` z nową sekcją. \
Opcjonalnie inne pola jeśli wymagają poprawki.
- `changes`: NIE dodawaj dla DELETE
- `problems`: WYMAGANE dla obu statusów — opisz co znalazłeś lub dlaczego potwierdzasz DELETE
- Explanation musi mieć format referencji: `%(instruction)s § X ust. Y pkt Z`

WAŻNE: Musisz użyć Write tool aby zapisać plik JSON z wynikami.
"""


def extract_candidates(
    name: str, section_filter: str | None = None,
) -> list[dict]:
    """Extract DELETE candidates from verification and questions files."""
    base = INSTRUCTIONS_DIR / name
    v_path = base / f"{name}-verification.json"
    q_path = base / f"{name}-pytania.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found", file=sys.stderr)
        sys.exit(1)
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    v_data = json.loads(v_path.read_text(encoding="utf-8"))
    q_data = json.loads(q_path.read_text(encoding="utf-8"))

    q_lookup = {q["uuid"]: q for q in q_data["questions"]}

    delete_entries = {
        r["uuid"]: r.get("problems", [])
        for r in v_data["results"]
        if r["status"] == "DELETE"
    }

    def section_matches(ref: str) -> bool:
        if section_filter is None:
            return True
        normalized = re.sub(r"\s+", "", ref or "")
        return normalized == f"§{section_filter}"

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

    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare rescue batches with agent prompts.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--section", type=str, help="Filter by section number (e.g. 5, 12)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Max questions per batch (default: {BATCH_SIZE})",
    )
    args = parser.parse_args()

    section = args.section.strip() if args.section else None
    candidates = extract_candidates(args.name, section)

    if not candidates:
        print("Brak pytań DELETE do rescue.", file=sys.stderr)
        manifest = {
            "instruction": args.name,
            "total_candidates": 0,
            "batch_count": 0,
            "batches": [],
        }
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    # Read TOC
    toc_path = INSTRUCTIONS_DIR / args.name / f"{args.name}-spis-tresci.md"
    if not toc_path.exists():
        print(
            f"Error: {toc_path} not found. Run: make toc ONLY={args.name}",
            file=sys.stderr,
        )
        sys.exit(1)
    toc_content = toc_path.read_text(encoding="utf-8")

    # Prepare output directory
    tmp_dir = Path(f"/tmp/rescue-{args.name}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for f in tmp_dir.glob("*.json"):
        f.unlink()
    for f in tmp_dir.glob("*.md"):
        f.unlink()

    # Group into batches and generate prompts
    batches = []
    for i in range(0, len(candidates), args.batch_size):
        batch_candidates = candidates[i : i + args.batch_size]
        batch_num = len(batches) + 1

        input_path = tmp_dir / f"input_batch_{batch_num}.json"
        output_path = tmp_dir / f"batch_{batch_num}.json"
        prompt_path = tmp_dir / f"prompt_batch_{batch_num}.md"

        input_path.write_text(
            json.dumps(batch_candidates, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        prompt = PROMPT_TEMPLATE % {
            "instruction": args.name,
            "toc_content": toc_content,
            "questions_json": json.dumps(
                batch_candidates, ensure_ascii=False, indent=2,
            ),
            "output_path": str(output_path),
        }
        prompt_path.write_text(prompt, encoding="utf-8")

        batches.append({
            "batch": batch_num,
            "count": len(batch_candidates),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "prompt_path": str(prompt_path),
        })

    manifest = {
        "instruction": args.name,
        "total_candidates": len(candidates),
        "batch_count": len(batches),
        "batches": batches,
    }

    if section:
        print(
            f"DELETE: {len(candidates)} matching § {section}"
            f" → {len(batches)} batches",
            file=sys.stderr,
        )
    else:
        print(
            f"DELETE: {len(candidates)} candidates"
            f" → {len(batches)} batches",
            file=sys.stderr,
        )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
