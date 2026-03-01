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

Jeśli podano `section_filter`, zamień na format `§ {numer}` (np. `5` → `§ 5`) — rescue tylko pytania DELETE z tego paragrafu.

Jeśli brak pierwszego argumentu, wypisz błąd: `Użycie: /rescue-questions <instruction> [numer-paragrafu]` i zakończ.

## Procedura

### 1. Wczytaj dane

Wczytaj `instructions/{instruction}/{instruction}-verification.json`:
- Wyfiltruj entries ze statusem `DELETE` → to są kandydaci do rescue
- Zapamiętaj ich UUID i `problems` (powody DELETE)

Wczytaj `instructions/{instruction}/{instruction}-pytania.json`:
- Wyciągnij pełne pytania (question, answers, correct, explanation, section_ref) po UUID kandydatów
- Jeśli podano `section_filter`, odfiltruj do pytań z pasującym `section_ref` (porównuj ignorując spacje, np. `§12` pasuje do `§ 12`)

Jeśli 0 pytań DELETE (po filtrze) → wypisz `Brak pytań DELETE do rescue w {instruction}.` i zakończ.

Wypisz: `Rescue {instruction}: {N} pytań DELETE do sprawdzenia` (jeśli filtrowane, dodaj `(§ X)`)

### 2. Wczytaj spis treści

Sprawdź czy istnieje `instructions/{instruction}/{instruction}-spis-tresci.md`.
- Jeśli nie istnieje, wypisz błąd: `Brak spisu treści. Wygeneruj go: make toc ONLY={instruction}` i zakończ.
- Wczytaj zawartość spisu treści.

### 3. Utwórz katalog na wyniki

```bash
rm -rf /tmp/rescue-{instruction} && mkdir -p /tmp/rescue-{instruction}
```

### 4. Pogrupuj i odpal agentów

Podziel pytania DELETE na grupy po **max 8 pytań**. Dla każdej grupy odpal agenta:
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
