"""Prepare verification batches: group questions by section, generate agent prompts.

Groups questions from pytania.json by section_ref, splits into batches
of max 8, generates agent prompts, and outputs a manifest.

Supports RESCUED mode: re-verifies questions that were rescued with a new
section_ref from verification.json.

Usage:
    uv run python scripts/prepare_verify_batches.py Ir-1
    uv run python scripts/prepare_verify_batches.py Ir-1 --section 5
    uv run python scripts/prepare_verify_batches.py Ir-1 --rescued
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

## Zadanie

1. Przeczytaj plik sekcji: instructions/%(instruction)s/sections/%(section_ref)s.md
2. Zweryfikuj poniższe pytania
3. Zapisz wyniki do pliku: %(output_path)s

## Pytania do weryfikacji

%(questions_json)s

## Dla każdego pytania sprawdź

1. Czy **poprawna odpowiedź** (`correct`) faktycznie wynika z treści paragrafu?
2. Czy **pytanie** jest jednoznaczne, precyzyjne i poprawne językowo (polska gramatyka)?
3. Czy **dokładnie jedna** odpowiedź jest poprawna według treści paragrafu? Jeśli więcej niż jedna \
odpowiedź ma pokrycie w treści — oznacz DELETE (pytanie niejednoznaczne).
4. Czy **błędne odpowiedzi** (dystraktory) są wiarygodne ale faktycznie niepoprawne?
   - Przy pytaniach definicyjnych (np. "Jak instrukcja definiuje pojęcie X?") dystraktory powinny być \
definicjami innych pojęć z tego samego paragrafu/instrukcji — nie krótkimi, oczywiście błędnymi hasłami. \
Jeśli dystraktory są zbyt łatwe do odrzucenia (np. krótkie frazy vs. długa definicja), oznacz FIX \
i zaproponuj dystraktory będące definicjami innych pojęć z tego samego paragrafu lub instrukcji.
5. Czy `explanation` wskazuje właściwy paragraf, ustęp i podpunkt (jeśli jest w danym ustępie)?
6. Czy `explanation` ma poprawny format źródła? Dozwolony format to **wyłącznie** referencja do paragrafu, np.:
   - `%(instruction)s § 63 ust. 6 pkt 2` (nazwa instrukcji + paragraf + opcjonalnie ustęp, punkt, litera)
   - `%(instruction)s § 63 ust. 6 pkt 2 tabela poz. 42` (z opcjonalnym odwołaniem do tabeli)
   - Niedozwolone: dodatkowy tekst opisowy, komentarze w nawiasach, "w zw. z", "w powiązaniu z", myślniki z wyjaśnieniami, "par." zamiast "§", itp.
   - Jeśli explanation zawiera cokolwiek poza czystą referencją — oznacz jako FIX i podaj poprawioną wersję zawierającą tylko referencję
   - Jeśli explanation jest puste lub brak go — znajdź właściwy paragraf/ustęp w treści sekcji i dodaj referencję
7. Czy nie ma literówek, powtórzeń, nielogicznych sformułowań, nadmiarowych słów których nie ma w danym paragrafie/ustępie?
8. Czy pytanie nie jest **duplikatem** innego pytania w tej samej sekcji (ta sama treść lub ten sam sens, ta sama poprawna odpowiedź)? \
Jeśli tak — oznacz jako DELETE **tylko jedno** z duplikatów (to gorsze/mniej precyzyjne), a lepsze zachowaj z odpowiednim statusem (OK lub FIX).

## Format wyników — ZAPISZ DO PLIKU

Po weryfikacji, użyj narzędzia **Bash** z komendą `python3` aby zapisać wyniki do pliku \
`%(output_path)s`. Przykład:

```bash
python3 << 'PYEOF'
import json

data = [
  {
    "uuid": "...",
    "status": "OK",
    "problems": []
  },
  {
    "uuid": "...",
    "status": "FIX",
    "problems": ["Literówka: 'dyzurnego' → 'dyżurnego'"],
    "changes": {
      "question": "poprawiona treść"
    }
  },
  {
    "uuid": "...",
    "status": "DELETE",
    "problems": ["Treść nie wynika z podanego paragrafu"]
  }
]

with open("%(output_path)s", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\\n")
PYEOF
```

Zasady:
- **Zawsze preferuj FIX nad DELETE** — usuwaj pytanie tylko gdy nie da się go sensownie naprawić \
(np. jest duplikatem innego pytania, treść w ogóle nie wynika z paragrafu). Jeśli pytanie ma \
niejednoznaczne odpowiedzi, błędne dystraktory, nieprecyzyjne sformułowanie — popraw je (FIX), nie usuwaj.
- `status`: OK (bez zmian), FIX (wymaga poprawek), DELETE (do usunięcia)
- `changes`: tylko dla FIX — zawiera TYLKO pola które się zmieniają. Dla DELETE i OK — nie dodawaj `changes`.
- `problems`: **WYMAGANE** dla FIX i DELETE — lista stringów opisujących co jest nie tak. NIGDY nie zostawiaj pustej listy `[]` dla FIX/DELETE!
  - Dla FIX: opisz KAŻDY problem który wymaga poprawki (np. "Literówka: 'dyzurnego' → 'dyżurnego'", "Brak słowa 'kolejowego' w odpowiedzi B")
  - Dla DELETE: opisz KAŻDY powód usunięcia (np. "Duplikat pytania uuid=abc123", "Treść nie wynika z podanego paragrafu")
  - Dla OK: pusta lista `[]` lub drobne uwagi niewymagające zmian
- Używaj DOKŁADNIE tych nazw pól: `uuid`, `status`, `problems`, `changes`. NIE używaj innych nazw jak `issues`, `reason`, `fix`, `corrections` itp.
- Każdy element `problems` musi być pełnym zdaniem opisującym problem, nie pustym stringiem.

WAŻNE: Do zapisu pliku użyj Bash z python3 (jak w przykładzie powyżej). NIE używaj Write tool.
"""


def sanitize_ref(ref: str) -> str:
    """Sanitize section_ref for use in filenames: '§ 12' -> '§12'."""
    return re.sub(r"\s+", "", ref)


def load_questions_normal(
    name: str, section_filter: str | None,
) -> list[dict]:
    """Load questions from pytania.json, optionally filtered by section."""
    q_path = INSTRUCTIONS_DIR / name / f"{name}-pytania.json"
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    q_data = json.loads(q_path.read_text(encoding="utf-8"))
    questions = q_data["questions"]

    if section_filter:
        target = f"§{section_filter}"
        questions = [
            q for q in questions
            if sanitize_ref(q.get("section_ref") or "") == target
        ]

    return questions


def load_questions_rescued(name: str) -> list[dict]:
    """Load RESCUED questions with overridden section_ref from changes."""
    v_path = INSTRUCTIONS_DIR / name / f"{name}-verification.json"
    q_path = INSTRUCTIONS_DIR / name / f"{name}-pytania.json"

    if not v_path.exists():
        print(f"Error: {v_path} not found", file=sys.stderr)
        sys.exit(1)
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    v_data = json.loads(v_path.read_text(encoding="utf-8"))
    q_data = json.loads(q_path.read_text(encoding="utf-8"))

    q_lookup = {q["uuid"]: q for q in q_data["questions"]}

    rescued_entries = [
        r for r in v_data["results"] if r["status"] == "RESCUED"
    ]

    questions = []
    for entry in rescued_entries:
        uuid = entry["uuid"]
        q = q_lookup.get(uuid)
        if not q:
            continue
        # Override section_ref with the rescued one
        new_ref = entry.get("changes", {}).get("section_ref")
        if new_ref:
            q = dict(q)  # copy
            q["section_ref"] = new_ref
        questions.append(q)

    return questions


def group_by_section(questions: list[dict]) -> dict[str, list[dict]]:
    """Group questions by section_ref. Skip questions without section_ref."""
    groups: dict[str, list[dict]] = {}
    skipped = []
    for q in questions:
        ref = q.get("section_ref") or ""
        if not ref.strip():
            skipped.append(q.get("uuid", "?"))
            continue
        groups.setdefault(ref, []).append(q)

    if skipped:
        print(
            f"Warning: {len(skipped)} questions without section_ref skipped: "
            + ", ".join(skipped[:5])
            + ("..." if len(skipped) > 5 else ""),
            file=sys.stderr,
        )

    return groups


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare verification batches with agent prompts.",
    )
    parser.add_argument("name", help="Instruction name (e.g. Ir-1)")
    parser.add_argument(
        "--section", type=str, help="Filter by section number (e.g. 5, 12)",
    )
    parser.add_argument(
        "--rescued", action="store_true",
        help="RESCUED mode: re-verify questions rescued with new section_ref",
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Max questions per batch (default: {BATCH_SIZE})",
    )
    args = parser.parse_args()

    # Load questions
    if args.rescued:
        questions = load_questions_rescued(args.name)
        mode_label = "RESCUED"
    else:
        section = args.section.strip() if args.section else None
        questions = load_questions_normal(args.name, section)
        mode_label = f"§ {section}" if section else "all"

    if not questions:
        print(f"Brak pytań do weryfikacji ({mode_label}).", file=sys.stderr)
        manifest = {
            "instruction": args.name,
            "mode": "rescued" if args.rescued else "normal",
            "total_questions": 0,
            "batch_count": 0,
            "batches": [],
        }
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    # Group by section
    groups = group_by_section(questions)

    # Prepare output directory
    tmp_dir = Path(f".tmp/verify-{args.name}").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for f in tmp_dir.glob("*.json"):
        f.unlink()
    for f in tmp_dir.glob("*.md"):
        f.unlink()

    # Split groups into batches of max batch_size and generate prompts
    batches = []
    for section_ref, section_questions in sorted(groups.items()):
        for part_idx in range(0, len(section_questions), args.batch_size):
            batch_questions = section_questions[
                part_idx : part_idx + args.batch_size
            ]
            part_num = part_idx // args.batch_size + 1
            total_parts = (
                len(section_questions) + args.batch_size - 1
            ) // args.batch_size

            # Agent ID for filename
            ref_clean = sanitize_ref(section_ref)
            if total_parts > 1:
                agent_id = f"{ref_clean}_part{part_num}"
            else:
                agent_id = ref_clean

            output_path = tmp_dir / f"{agent_id}.json"
            prompt_path = tmp_dir / f"prompt_{agent_id}.md"

            prompt = PROMPT_TEMPLATE % {
                "instruction": args.name,
                "section_ref": section_ref,
                "output_path": str(output_path),
                "questions_json": json.dumps(
                    batch_questions, ensure_ascii=False, indent=2,
                ),
            }
            prompt_path.write_text(prompt, encoding="utf-8")

            batches.append({
                "agent_id": agent_id,
                "section_ref": section_ref,
                "count": len(batch_questions),
                "output_path": str(output_path),
                "prompt_path": str(prompt_path),
            })

    manifest = {
        "instruction": args.name,
        "mode": "rescued" if args.rescued else "normal",
        "total_questions": len(questions),
        "batch_count": len(batches),
        "batches": batches,
    }

    total_q = len(questions)
    print(
        f"{mode_label}: {total_q} questions, {len(groups)} sections"
        f" → {len(batches)} batches",
        file=sys.stderr,
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
