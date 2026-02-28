---
name: verify-questions
description: Weryfikacja pytań quizowych względem paragrafów instrukcji
disable-model-invocation: true
user-invocable: true
argument-hint: [nazwa-instrukcji]
---

# Weryfikacja pytań quizowych

Weryfikuj pytania z pliku `instructions/$ARGUMENTS/$ARGUMENTS-pytania.json` względem paragrafów instrukcji w `instructions/$ARGUMENTS/sections/`.

## Procedura

### 1. Wczytaj pytania

Wczytaj `instructions/$ARGUMENTS/$ARGUMENTS-pytania.json`. Zapamiętaj liczbę pytań.

### 2. Pogrupuj pytania — 1 sekcja, max 8 pytań per agent

Pogrupuj pytania po wartości `section_ref`. Pytania bez `section_ref` (null) umieść w osobnej grupie "brak_ref".

Następnie podziel grupy tak, aby **każdy agent** miał:
- **Dokładnie 1 sekcję** do przeczytania (nie łącz sekcji w jednym agencie)
- **Maksymalnie 8 pytań** — jeśli sekcja ma więcej, podziel na podzbiory po max 8

Wynik: lista "zadań agenckich", każde z jednym `section_ref` i listą max 8 pytań.

### 3. Utwórz katalog na wyniki

```bash
mkdir -p /tmp/verify-$ARGUMENTS
```

### 4. Odpal agentów równolegle (batche po max 7)

Uruchom agentów w **batchach po max 7** (nie wszystkie naraz!). Każdy agent:
- model: **sonnet** (szybszy, mniejsze zużycie kontekstu)
- subagent_type: **general-purpose**
- run_in_background: **true**

Po każdym batchu poczekaj na zakończenie wszystkich agentów z batcha, potem uruchom kolejny.

#### Prompt dla agenta

Każdy agent dostaje prompt zawierający:
- Treść pytań z jego grupy (wklejone bezpośrednio w prompt jako JSON)
- Ścieżkę do **jednego** pliku sekcji do przeczytania
- Ścieżkę do pliku wynikowego do zapisania
- Instrukcje weryfikacji i formatu wyjścia

Prompt template (użyj f-stringa lub podstawienia):

```
Jesteś weryfikatorem pytań quizowych z instrukcji kolejowej $ARGUMENTS (PKP).

## Zadanie

1. Przeczytaj plik sekcji: instructions/$ARGUMENTS/sections/{section_ref}.md
2. Zweryfikuj poniższe pytania
3. Zapisz wyniki do pliku: /tmp/verify-$ARGUMENTS/{agent_id}.json

## Pytania do weryfikacji

{questions_json}

## Dla każdego pytania sprawdź

1. Czy **poprawna odpowiedź** (`correct`) faktycznie wynika z treści paragrafu?
2. Czy **pytanie** jest jednoznaczne, precyzyjne i poprawne językowo (polska gramatyka)?
3. Czy **błędne odpowiedzi** (dystraktory) są wiarygodne ale faktycznie niepoprawne?
4. Czy `explanation` wskazuje właściwy paragraf, ustęp i podpunkt (jeśli jest w danym ustępie)?
5. Czy `explanation` ma poprawny format źródła? Dozwolony format to **wyłącznie** referencja do paragrafu, np.:
   - `$ARGUMENTS § 63 ust. 6 pkt 2` (nazwa instrukcji + paragraf + opcjonalnie ustęp, punkt, litera)
   - `$ARGUMENTS § 63 ust. 6 pkt 2 tabela poz. 42` (z opcjonalnym odwołaniem do tabeli)
   - Niedozwolone: dodatkowy tekst opisowy, komentarze w nawiasach, "w zw. z", "w powiązaniu z", myślniki z wyjaśnieniami, "par." zamiast "§", itp.
   - Jeśli explanation zawiera cokolwiek poza czystą referencją — oznacz jako FIX i podaj poprawioną wersję zawierającą tylko referencję
   - Jeśli explanation jest puste lub brak go — znajdź właściwy paragraf/ustęp w treści sekcji i dodaj referencję
6. Czy nie ma literówek, powtórzeń, nielogicznych sformułowań, nadmiarowych słów których nie ma w danym paragrafie/ustępie?

## Format wyników — ZAPISZ DO PLIKU

Po weryfikacji, użyj narzędzia Write aby zapisać wyniki jako JSON do pliku /tmp/verify-$ARGUMENTS/{agent_id}.json:

[
  {
    "uuid": "...",
    "status": "OK|FIX|DELETE",
    "problems": ["opis problemu 1", "opis problemu 2"],
    "changes": {
      "question": "nowa treść (tylko jeśli zmieniona)",
      "answers": {"A": "...", "B": "..."},
      "correct": "B",
      "explanation": "Ir-1 § X ust. Y"
    }
  }
]

Zasady:
- `status`: OK (bez zmian), FIX (wymaga poprawek), DELETE (do usunięcia)
- `changes`: tylko dla FIX — zawiera TYLKO pola które się zmieniają. Dla DELETE i OK — nie dodawaj `changes`.
- `problems`: **WYMAGANE** dla FIX i DELETE — lista stringów opisujących co jest nie tak. NIGDY nie zostawiaj pustej listy `[]` dla FIX/DELETE!
  - Dla FIX: opisz KAŻDY problem który wymaga poprawki (np. "Literówka: 'dyzurnego' → 'dyżurnego'", "Brak słowa 'kolejowego' w odpowiedzi B")
  - Dla DELETE: opisz KAŻDY powód usunięcia (np. "Duplikat pytania uuid=abc123", "Treść nie wynika z podanego paragrafu")
  - Dla OK: pusta lista `[]` lub drobne uwagi niewymagające zmian
- Używaj DOKŁADNIE tych nazw pól: `uuid`, `status`, `problems`, `changes`. NIE używaj innych nazw jak `issues`, `reason`, `fix`, `corrections` itp.
- Każdy element `problems` musi być pełnym zdaniem opisującym problem, nie pustym stringiem.

WAŻNE: Musisz użyć Write tool aby zapisać plik JSON z wynikami. To jest Twoje główne zadanie.
```

Gdzie `{agent_id}` to unikalny identyfikator, np. `{section_ref}_part{N}` (np. `§12_part1`, `§84_part1`, `§84_part2`).

### 5. Zbierz i zwaliduj wyniki z plików

Po zakończeniu wszystkich agentów, wczytaj wszystkie pliki JSON z `/tmp/verify-$ARGUMENTS/`:

```bash
ls /tmp/verify-$ARGUMENTS/*.json
```

Przeczytaj każdy plik, połącz wszystkie wyniki w jedną listę.

**Walidacja wyników** — dla każdego wyniku sprawdź:
- Czy ma wymagane pola: `uuid`, `status`, `problems`
- Czy `status` jest jednym z: `OK`, `FIX`, `DELETE`
- Czy dla FIX/DELETE pole `problems` jest **niepustą listą stringów** (nie `[]`, nie `null`, nie `[""]`)
- Czy dla FIX pole `changes` istnieje i nie jest puste `{}`
- Jeśli agent użył niestandardowych pól (np. `issues` zamiast `problems`, `reason` zamiast `problems`), spróbuj je zmapować na poprawne nazwy

Jeśli walidacja wykryje braki, wypisz ostrzeżenie z UUID pytań z problemami.

**Mapowanie niestandardowych pól:**
- `issues` → `problems`
- `reason`/`reasons` → `problems` (opakuj w listę jeśli to string)
- `fix`/`corrections`/`suggested_changes` → `changes`

### 6. Utwórz raport

Sparsuj wyniki i utwórz raport JSON:

```json
{
  "instruction": "$ARGUMENTS",
  "timestamp": "2026-02-28T...",
  "summary": {
    "total": 155,
    "ok": 120,
    "fix": 25,
    "delete": 10
  },
  "results": [
    {
      "uuid": "...",
      "status": "OK|FIX|DELETE",
      "problems": ["..."],
      "changes": {
        "question": "nowa treść",
        "answers": {"A": "..."},
        "correct": "B",
        "explanation": "..."
      }
    }
  ]
}
```

### 7. Zapisz raport

Zapisz raport do `instructions/$ARGUMENTS/$ARGUMENTS-verification.json`.

Wypisz podsumowanie:
```
Weryfikacja $ARGUMENTS: X pytań OK, Y do poprawy, Z do usunięcia
```

### 8. Zapytaj użytkownika

Użyj AskUserQuestion aby zapytać:
- "Czy zastosować poprawki (FIX/DELETE) na pytaniach?" z opcjami:
  - "Tak, zastosuj wszystkie" — zastosuj FIX i DELETE
  - "Pokaż szczegóły najpierw" — wypisz wszystkie FIX i DELETE ze szczegółami
  - "Nie, tylko zapisz raport" — zakończ

### 9. Zastosuj poprawki (jeśli użytkownik potwierdzi)

Wczytaj `instructions/$ARGUMENTS/$ARGUMENTS-pytania.json`. Dla każdego wyniku:
- **FIX**: zastosuj zmiany z `changes` na odpowiednim pytaniu (dopasowanie po `uuid`)
- **DELETE**: usuń pytanie z listy

Zapisz zaktualizowany plik. Wypisz:
```
Zastosowano: X poprawek, Y usunięć. Pozostało Z pytań.
```
