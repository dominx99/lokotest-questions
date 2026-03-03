"""Prepare verification batches: group questions by section, generate agent prompts.

Groups questions from pytania.json by section_ref, splits into batches
of max 30, generates agent prompts, and outputs a manifest.

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
BATCH_SIZE = 30

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
2. Czy **pytanie** jest jednoznaczne, precyzyjne i poprawne językowo (polska gramatyka)? \
Treść pytania **NIE MOŻE** zawierać referencji do instrukcji, paragrafów, ustępów ani punktów \
(np. "zgodnie z § 2 ust. 6 pkt 1 Ir-1"). Takie informacje należą wyłącznie do pola `explanation`. \
Pytanie powinno być zrozumiałe bez znajomości numeracji paragrafów. Jeśli pytanie zawiera takie referencje — oznacz FIX i usuń je z treści pytania.
3. Czy **dokładnie jedna** odpowiedź jest poprawna według treści paragrafu? Jeśli więcej niż jedna \
odpowiedź ma pokrycie w treści — oznacz DELETE (pytanie niejednoznaczne).
4. Czy **błędne odpowiedzi** (dystraktory) są wiarygodne ale faktycznie niepoprawne?
   - Dystraktory muszą być z **tej samej kategorii semantycznej** co poprawna odpowiedź. \
Jeśli poprawna odpowiedź definiuje miejsce/obszar — dystraktory też muszą być definicjami miejsc/obszarów. \
Jeśli definiuje osobę/rolę — dystraktory muszą być definicjami innych osób/ról. Itd.
   - **Priorytet 1**: użyj definicji innych pojęć z tej samej kategorii semantycznej z tego samego paragrafu \
(np. pytanie o „rejon manewrowy" → dystraktory z definicji innych miejsc/obszarów z tego paragrafu).
   - **Priorytet 2**: jeśli w paragrafie brak wystarczającej liczby pojęć z tej samej kategorii — \
weź poprawną definicję i **zmień w niej kluczowe słowa/frazy** tak, aby była niepoprawna ale brzmiała wiarygodnie \
(np. „wydzielony pod względem organizacji i technologii manewrów" → „wydzielony pod względem organizacji \
i technologii ruchu pociągów"). To testuje dokładną znajomość definicji.
   - Jeśli dystraktory nie spełniają powyższych zasad (np. definicja urządzenia jako dystraktor \
do pytania o miejsce) — oznacz FIX i zaproponuj poprawione dystraktory.
5. Czy `explanation` wskazuje właściwy paragraf, ustęp i podpunkt (jeśli jest w danym ustępie)?
6. Czy `explanation` ma poprawny format źródła? Dozwolony format to **wyłącznie** referencja do paragrafu, np.:
   - `%(instruction)s § 63 ust. 6 pkt 2` (nazwa instrukcji + paragraf + opcjonalnie ustęp, punkt, litera)
   - `%(instruction)s § 63 ust. 6 pkt 2 tabela poz. 42` (z opcjonalnym odwołaniem do tabeli)
   - Niedozwolone: dodatkowy tekst opisowy, komentarze w nawiasach, "w zw. z", "w powiązaniu z", myślniki z wyjaśnieniami, "par." zamiast "§", itp.
   - Jeśli explanation zawiera cokolwiek poza czystą referencją — oznacz jako FIX i podaj poprawioną wersję zawierającą tylko referencję
   - Jeśli explanation jest puste lub brak go — znajdź właściwy paragraf/ustęp w treści sekcji i dodaj referencję
7. Czy nie ma literówek, powtórzeń, nielogicznych sformułowań, nadmiarowych słów których nie ma w danym paragrafie/ustępie?
8. Czy pytanie nie jest **duplikatem** innego pytania w tej samej sekcji (ta sama treść lub ten sam sens **I** ta sama poprawna odpowiedź)? \
Jeśli tak — oznacz jako DELETE **tylko jedno** z duplikatów (to gorsze/mniej precyzyjne), a lepsze zachowaj z odpowiednim statusem (OK lub FIX). \
UWAGA: Jeśli dwa pytania mają identyczną treść, ale **różne poprawne odpowiedzi** (np. testują różne elementy z tego samego wyliczenia), to NIE są duplikatami — oba zachowaj.
9. Czy **poprawna odpowiedź lub dystraktory** nie są zbyt długie? Jeśli poprawna odpowiedź zawiera wyliczenie \
kilku podpunktów (np. definicja składająca się z 3-4 członów), oznacz pytanie jako DELETE z opisem problemu, \
a następnie zaproponuj **osobne pytania** (status NEW) — po jednym na każdy podpunkt/człon wyliczenia. \
Każde nowe pytanie powinno testować wiedzę o jednym konkretnym aspekcie definicji/wyliczenia. \
Wygeneruj UUID dla każdego nowego pytania za pomocą pythona: `import uuid; str(uuid.uuid4())`.
10. Czy **poprawna odpowiedź jest najdłuższa** spośród 4 opcji i >1,5× dłuższa od najdłuższego dystraktora? \
Jeśli tak — oznacz FIX. Wyrównaj **dystraktory w górę** do długości poprawnej odpowiedzi \
(rozbuduj je o treść z paragrafu). Nie modyfikuj poprawnej odpowiedzi tylko dla wyrównania długości. \
Jeśli poprawna odpowiedź jest **krótsza** od dystraktorów — to NIE jest problem, oznacz OK. \
Nie „napompowuj" dystraktorów bezsensownym tekstem — ich szczegółowość musi wynikać z treści paragrafu.

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
  },
  {
    "uuid": "<nowy-uuid-wygenerowany-przez-uuid4>",
    "status": "NEW",
    "problems": ["Rozbicie pytania o zbyt długiej odpowiedzi na osobne pytania"],
    "changes": {
      "question": "Treść nowego pytania?",
      "answers": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "B",
      "explanation": "%(instruction)s § X ust. Y",
      "section_ref": "§ X"
    }
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
- `status`: OK (bez zmian), FIX (wymaga poprawek), DELETE (do usunięcia), NEW (nowe pytanie — zastępuje usunięte)
- `changes`: tylko dla FIX — zawiera TYLKO pola które się zmieniają. Dla DELETE i OK — nie dodawaj `changes`. \
Dla NEW — `changes` musi zawierać kompletne pytanie: `question`, `answers`, `correct`, `explanation`, `section_ref`.
- `problems`: **WYMAGANE** dla FIX, DELETE i NEW — lista stringów opisujących co jest nie tak. NIGDY nie zostawiaj pustej listy `[]` dla FIX/DELETE/NEW!
  - Dla FIX: opisz KAŻDY problem który wymaga poprawki (np. "Literówka: 'dyzurnego' → 'dyżurnego'", "Brak słowa 'kolejowego' w odpowiedzi B")
  - Dla DELETE: opisz KAŻDY powód usunięcia (np. "Duplikat pytania uuid=abc123", "Treść nie wynika z podanego paragrafu")
  - Dla NEW: opisz dlaczego pytanie zostało utworzone (np. "Rozbicie pytania uuid=abc123 o zbyt długiej odpowiedzi")
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
    section_range: tuple[int, int] | None = None,
) -> list[dict]:
    """Load questions from pytania.json, optionally filtered by section."""
    q_path = INSTRUCTIONS_DIR / name / f"{name}-pytania.json"
    if not q_path.exists():
        print(f"Error: {q_path} not found", file=sys.stderr)
        sys.exit(1)

    q_data = json.loads(q_path.read_text(encoding="utf-8"))
    questions = q_data["questions"]

    # Skip already verified questions
    before = len(questions)
    questions = [q for q in questions if not q.get("verified")]
    skipped_verified = before - len(questions)
    if skipped_verified:
        print(
            f"Pominięto {skipped_verified} zweryfikowanych pytań.",
            file=sys.stderr,
        )

    if section_filter:
        target = f"§{section_filter}"
        questions = [
            q for q in questions
            if sanitize_ref(q.get("section_ref") or "") == target
        ]

    if section_range:
        range_start, range_end = section_range
        filtered = []
        for q in questions:
            ref = sanitize_ref(q.get("section_ref") or "")
            m = re.match(r"§(\d+)", ref)
            if m and range_start <= int(m.group(1)) <= range_end:
                filtered.append(q)
        questions = filtered

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
        "--section-range", type=str,
        help="Filter by section range (e.g. 1-30, 25-85)",
    )
    parser.add_argument(
        "--uuid", type=str, help="Filter by question UUID",
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
    elif args.uuid:
        questions = load_questions_normal(args.name, None)
        questions = [q for q in questions if q["uuid"] == args.uuid]
        mode_label = f"UUID {args.uuid[:8]}..."
    else:
        section = args.section.strip() if args.section else None
        section_range = None
        if args.section_range:
            m = re.match(r"^(\d+)-(\d+)$", args.section_range.strip())
            if not m:
                print(
                    "Error: --section-range must be in format N-M (e.g. 1-30)",
                    file=sys.stderr,
                )
                sys.exit(1)
            section_range = (int(m.group(1)), int(m.group(2)))
        questions = load_questions_normal(args.name, section, section_range)
        if section:
            mode_label = f"§ {section}"
        elif section_range:
            mode_label = f"§ {section_range[0]}-{section_range[1]}"
        else:
            mode_label = "all"

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

    # Split groups into batches of max batch_size, distributed evenly
    batches = []
    for section_ref, section_questions in sorted(groups.items()):
        n = len(section_questions)
        total_parts = (n + args.batch_size - 1) // args.batch_size
        base = n // total_parts
        remainder = n % total_parts
        # First `remainder` batches get base+1, rest get base
        offset = 0
        for part_num in range(1, total_parts + 1):
            size = base + (1 if part_num <= remainder else 0)
            batch_questions = section_questions[offset : offset + size]
            offset += size

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
