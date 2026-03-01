---
name: verify-questions
description: Weryfikacja pytań quizowych względem paragrafów instrukcji
disable-model-invocation: true
user-invocable: true
argument-hint: [nazwa-instrukcji] [numer-paragrafu|RESCUED]
---

# Weryfikacja pytań quizowych

Weryfikuj pytania z pliku `instructions/{instruction}/{instruction}-pytania.json` względem paragrafów instrukcji w `instructions/{instruction}/sections/`.

## Parsowanie argumentów

Rozparsuj `$ARGUMENTS` na:
- **instruction** — pierwszy argument (wymagany), np. `Ir-1`
- **drugi argument** (opcjonalny), jedno z:
  - **numer paragrafu** (np. `5` lub `12`) → `section_filter` = `§ {numer}`
  - **`RESCUED`** (case-insensitive) → tryb RESCUED

**Tryb normalny (section_filter):** weryfikuj **tylko** pytania z pasującym `section_ref`. Bez drugiego argumentu — weryfikuj wszystkie.

**Tryb RESCUED:** weryfikuj ponownie pytania ze statusem RESCUED z `{instruction}-verification.json` — patrz sekcja "Tryb RESCUED" poniżej.

## Procedura

### 1. Wczytaj pytania

**Tryb RESCUED** — jeśli drugi argument to `RESCUED`:

1. Wczytaj `instructions/{instruction}/{instruction}-verification.json`
2. Wyfiltruj entries ze statusem `RESCUED`
3. Dla każdego entry weź UUID i `changes.section_ref` jako nowy section_ref
4. Wczytaj `instructions/{instruction}/{instruction}-pytania.json`
5. Pobierz pełne pytania po UUID
6. **Nadpisz `section_ref` każdego pytania** wartością z verification changes (to jest nowa sekcja znaleziona przez rescue)
7. Jeśli 0 pytań RESCUED → wypisz komunikat i zakończ

**Tryb normalny:**

Wczytaj `instructions/{instruction}/{instruction}-pytania.json`. Zapamiętaj liczbę pytań.

Jeśli podano `section_filter`, odfiltruj pytania do tych z pasującym `section_ref` (porównuj ignorując spacje, np. `§12` pasuje do `§ 12`). Wypisz ile pytań zostało po filtrze.

### 2. Pogrupuj pytania — 1 sekcja, max 8 pytań per agent

Pogrupuj pytania po wartości `section_ref`. **Pytania bez `section_ref` (null/pusty) pomiń** — wypisz ich liczbę i UUID jako ostrzeżenie, ale nie weryfikuj ich.

Następnie podziel grupy tak, aby **każdy agent** miał:
- **Dokładnie 1 sekcję** do przeczytania (nie łącz sekcji w jednym agencie)
- **Maksymalnie 8 pytań** — jeśli sekcja ma więcej, podziel na podzbiory po max 8

Wynik: lista "zadań agenckich", każde z jednym `section_ref` i listą max 8 pytań.

### 3. Utwórz katalog na wyniki

```bash
mkdir -p /tmp/verify-{instruction} && find /tmp/verify-{instruction} -name "*.json" -delete
```

### 4. Odpal WSZYSTKICH agentów naraz

Uruchom **wszystkich** agentów w jednym wywołaniu (jednym message z wieloma tool calls). Claude Code sam zakolejkuje ich do swojego wewnętrznego limitu równoległości. Każdy agent:
- model: **sonnet** (szybszy, mniejsze zużycie kontekstu)
- subagent_type: **general-purpose**
- run_in_background: **true**

Po odpaleniu wszystkich, czekaj na ich zakończenie (notyfikacje przychodzą automatycznie).

#### Prompt dla agenta

Każdy agent dostaje prompt zawierający:
- Treść pytań z jego grupy (wklejone bezpośrednio w prompt jako JSON)
- Ścieżkę do **jednego** pliku sekcji do przeczytania
- Ścieżkę do pliku wynikowego do zapisania
- Instrukcje weryfikacji i formatu wyjścia

Prompt template (użyj f-stringa lub podstawienia):

```
Jesteś weryfikatorem pytań quizowych z instrukcji kolejowej {instruction} (PKP).

## Zadanie

1. Przeczytaj plik sekcji: instructions/{instruction}/sections/{section_ref}.md
2. Zweryfikuj poniższe pytania
3. Zapisz wyniki do pliku: /tmp/verify-{instruction}/{agent_id}.json

## Pytania do weryfikacji

{questions_json}

## Dla każdego pytania sprawdź

1. Czy **poprawna odpowiedź** (`correct`) faktycznie wynika z treści paragrafu?
2. Czy **pytanie** jest jednoznaczne, precyzyjne i poprawne językowo (polska gramatyka)?
3. Czy **błędne odpowiedzi** (dystraktory) są wiarygodne ale faktycznie niepoprawne?
4. Czy `explanation` wskazuje właściwy paragraf, ustęp i podpunkt (jeśli jest w danym ustępie)?
5. Czy `explanation` ma poprawny format źródła? Dozwolony format to **wyłącznie** referencja do paragrafu, np.:
   - `{instruction} § 63 ust. 6 pkt 2` (nazwa instrukcji + paragraf + opcjonalnie ustęp, punkt, litera)
   - `{instruction} § 63 ust. 6 pkt 2 tabela poz. 42` (z opcjonalnym odwołaniem do tabeli)
   - Niedozwolone: dodatkowy tekst opisowy, komentarze w nawiasach, "w zw. z", "w powiązaniu z", myślniki z wyjaśnieniami, "par." zamiast "§", itp.
   - Jeśli explanation zawiera cokolwiek poza czystą referencją — oznacz jako FIX i podaj poprawioną wersję zawierającą tylko referencję
   - Jeśli explanation jest puste lub brak go — znajdź właściwy paragraf/ustęp w treści sekcji i dodaj referencję
6. Czy nie ma literówek, powtórzeń, nielogicznych sformułowań, nadmiarowych słów których nie ma w danym paragrafie/ustępie?

## Format wyników — ZAPISZ DO PLIKU

Po weryfikacji, użyj narzędzia Write aby zapisać wyniki jako JSON do pliku /tmp/verify-{instruction}/{agent_id}.json:

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

### 5. Zbierz wyniki — uruchom skrypt merge

Po zakończeniu wszystkich agentów, uruchom skrypt merge:

**Tryb normalny:**
```bash
uv run python scripts/merge_verification.py {instruction}
```

**Tryb RESCUED:**
```bash
uv run python scripts/merge_verification.py {instruction} --rescued
```

Skrypt:
- Wczyta wszystkie pliki JSON z `/tmp/verify-{instruction}/`
- Zwaliduje i znormalizuje wyniki (mapowanie niestandardowych pól, sprawdzenie wymaganych pól)
- **Tryb normalny**: utworzy/nadpisze `{instruction}-verification.json` z wszystkimi wynikami
- **Tryb RESCUED**: zastąpi entries RESCUED nowymi wynikami (FIX/OK/DELETE), zachowując pozostałe entries bez zmian
- Wypisze podsumowanie

Wypisz wynik skryptu jako podsumowanie.

### 6. Zapytaj użytkownika

Użyj AskUserQuestion aby zapytać:
- "Czy zastosować poprawki (FIX/DELETE) na pytaniach?" z opcjami:
  - "Tak, zastosuj wszystkie" — zastosuj FIX i DELETE
  - "Pokaż szczegóły najpierw" — wypisz wszystkie FIX i DELETE ze szczegółami
  - "Nie, tylko zapisz raport" — zakończ

### 7. Zastosuj poprawki (jeśli użytkownik potwierdzi)

Wczytaj `instructions/{instruction}/{instruction}-pytania.json`. Dla każdego wyniku:
- **FIX**: zastosuj zmiany z `changes` na odpowiednim pytaniu (dopasowanie po `uuid`)
- **DELETE**: usuń pytanie z listy

Zapisz zaktualizowany plik. Wypisz:
```
Zastosowano: X poprawek, Y usunięć. Pozostało Z pytań.
```
