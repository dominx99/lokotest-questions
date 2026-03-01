---
name: rescue-questions
description: Próba uratowania pytań DELETE — szukanie właściwej sekcji w instrukcji
disable-model-invocation: true
user-invocable: true
argument-hint: [nazwa-instrukcji] [numer-paragrafu]
---

# Rescue pytań DELETE

Na podstawie spisu treści wytypuj sekcje, które mogą zawierać pokrycie dla pytań oznaczonych DELETE, a następnie przeczytaj te sekcje aby zweryfikować.

## Parsowanie argumentów

Rozparsuj `$ARGUMENTS` na:
- **instruction** — pierwszy argument (wymagany), np. `Ir-1`
- **section_filter** — drugi argument (opcjonalny), sam numer paragrafu, np. `5` lub `12`

Jeśli podano `section_filter`, przekaż go **jako sam numer** (np. `5`, `12`) do skryptu przez `--section`. Skrypt sam obsługuje dopasowanie do `§ X`.

Jeśli brak pierwszego argumentu, wypisz błąd: `Użycie: /rescue-questions <instruction> [numer-paragrafu]` i zakończ.

## Procedura

### 1. Wyekstrahuj kandydatów do rescue

Uruchom skrypt, który wyciągnie pytania DELETE z verification.json i pytania.json:

**Bez filtra sekcji:**
```bash
uv run python scripts/extract_rescue_candidates.py {instruction}
```

**Z filtrem sekcji:**
```bash
uv run python scripts/extract_rescue_candidates.py {instruction} --section {section_filter}
```

Skrypt wypisze na stdout JSON z kandydatami (pełne pytania + `delete_problems`), a na stderr podsumowanie.

Jeśli lista jest pusta (`[]`) → wypisz `Brak pytań DELETE do rescue w {instruction}.` i zakończ.

Zapamiętaj wynik jako `candidates` (lista obiektów JSON).

### 2. Wczytaj spis treści

Wczytaj `instructions/{instruction}/{instruction}-spis-tresci.md` (Read tool).
- Jeśli nie istnieje, wypisz błąd: `Brak spisu treści. Wygeneruj go: make toc ONLY={instruction}` i zakończ.

### 3. Utwórz katalog na wyniki

```bash
mkdir -p /tmp/rescue-{instruction} && find /tmp/rescue-{instruction} -name "*.json" -delete
```

### 4. Pogrupuj i odpal agentów

Podziel `candidates` na grupy po **max 8 pytań**. Dla każdej grupy odpal agenta:
- model: **sonnet**
- subagent_type: **general-purpose**
- run_in_background: **true**

Odpal **WSZYSTKICH** agentów naraz w jednym wywołaniu (jednym message z wieloma tool calls).

### 5. Prompt agenta

```
Jesteś weryfikatorem pytań quizowych z instrukcji kolejowej {instruction} (PKP).

## Kontekst

Poniższe pytania zostały oznaczone jako DELETE podczas weryfikacji per-paragrafowej, ponieważ nie znaleziono dla nich pokrycia w przypisanej sekcji. Twoim zadaniem jest sprawdzić, czy pytanie ma pokrycie W INNEJ sekcji instrukcji.

## Spis treści instrukcji

{toc_content}

## Pytania do rescue

{questions_json_with_problems}

Dla każdego pytania w `questions_json_with_problems` jest podane:
- Pełne pytanie (question, answers, correct, explanation, section_ref)
- `delete_problems` — powody oznaczenia DELETE

## Procedura dla KAŻDEGO pytania

1. Przeczytaj treść pytania i powody DELETE
2. Na podstawie spisu treści wytypuj 1-3 sekcje, które mogą zawierać odpowiedź
3. Użyj Read tool aby przeczytać te sekcje: `instructions/{instruction}/sections/§X.md`
4. Zdecyduj:

   **RESCUED** — pytanie ma pokrycie w innej sekcji:
   - Podaj `section_ref` prawidłowej sekcji (np. `§ 42`)
   - Opcjonalnie popraw `question`, `answers`, `correct`, `explanation` jeśli trzeba je dostosować do nowej sekcji

   **DELETE** — potwierdzony DELETE, pytanie nie ma pokrycia nigdzie w instrukcji

## Format wyników — ZAPISZ DO PLIKU

Po weryfikacji, użyj narzędzia Write aby zapisać wyniki jako JSON do pliku {output_path}:

[
  {{
    "uuid": "...",
    "status": "RESCUED|DELETE",
    "problems": ["opis co znaleziono lub potwierdzenie braku pokrycia"],
    "changes": {{
      "section_ref": "§ X",
      "question": "nowa treść (tylko jeśli zmieniona)",
      "answers": {{"A": "..."}},
      "correct": "B",
      "explanation": "{instruction} § X ust. Y"
    }}
  }}
]

Zasady:
- `status`: RESCUED (znaleziono pokrycie w innej sekcji) lub DELETE (potwierdzony brak pokrycia)
- `changes`: **WYMAGANE** dla RESCUED — MUSI zawierać przynajmniej `section_ref` z nową sekcją. Opcjonalnie inne pola jeśli wymagają poprawki.
- `changes`: NIE dodawaj dla DELETE
- `problems`: WYMAGANE dla obu statusów — opisz co znalazłeś lub dlaczego potwierdzasz DELETE
- Explanation musi mieć format referencji: `{instruction} § X ust. Y pkt Z`

WAŻNE: Musisz użyć Write tool aby zapisać plik JSON z wynikami.
```

Gdzie `{output_path}` to `/tmp/rescue-{instruction}/batch_{N}.json`.

### 6. Zbierz wyniki — uruchom skrypt merge

Po zakończeniu wszystkich agentów, uruchom skrypt:

```bash
uv run python scripts/merge_rescue.py {instruction}
```

Skrypt:
- Wczyta wszystkie pliki JSON z `/tmp/rescue-{instruction}/`
- Zaktualizuje `{instruction}-verification.json`: zmieni status DELETE→RESCUED z `changes`, lub zostawi potwierdzone DELETE
- Przeliczy `summary` (z polem `rescued`)
- Wypisze podsumowanie

Wypisz wynik skryptu jako podsumowanie.
