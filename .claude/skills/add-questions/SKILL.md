---
name: add-questions
description: Generowanie brakujących pytań quizowych dla paragrafów instrukcji
disable-model-invocation: true
user-invocable: true
argument-hint: [nazwa-instrukcji] [numer-paragrafu|zakres-paragrafów]
---

# Generowanie brakujących pytań

Generuj nowe pytania quizowe dla paragrafów instrukcji, które mają zbyt mało pytań. Nowe pytania trafiają do pipeline weryfikacji ze statusem **NEW**.

## Parsowanie argumentów

Rozparsuj `$ARGUMENTS` na:
- **instruction** — pierwszy argument (wymagany), np. `Ir-1`
- **drugi argument** (opcjonalny), jedno z:
  - **numer paragrafu** (np. `5` lub `12`) → `section_filter`
  - **zakres paragrafów** (np. `1-30` lub `25-85`, format: `N-M` gdzie N ≤ M) → `section_range`

Jeśli brak pierwszego argumentu, wypisz błąd: `Użycie: /add-questions <instruction> [numer-paragrafu|zakres-paragrafów]` i zakończ.

## Procedura

### 1. Przygotuj batche

Uruchom skrypt, który obliczy deficyty pytań i wygeneruje prompty agentów:

**Bez filtra:**
```bash
uv run python scripts/prepare_add_batches.py {instruction}
```

**Z filtrem sekcji:**
```bash
uv run python scripts/prepare_add_batches.py {instruction} --section {section_filter}
```

**Z zakresem sekcji:**
```bash
uv run python scripts/prepare_add_batches.py {instruction} --section-range {section_range}
```

Skrypt:
- Obliczy deficyt pytań per sekcja
- Wypisze tabelę podsumowującą na stderr
- Wygeneruje gotowe prompty agentów w `.tmp/add-questions-{instruction}/prompt_*.md`
- Wypisze manifest JSON na stdout

Zapamiętaj manifest. Jeśli `total_to_add == 0`, wypisz komunikat i zakończ.

### 2. Odpal agentów

Dla każdego batcha z manifestu (`batches`) odpal agenta:
- prompt: `Przeczytaj plik {prompt_path} i wykonaj instrukcje w nim zawarte.`
- model: **sonnet**
- subagent_type: **general-purpose**
- mode: **bypassPermissions**
- run_in_background: **true**

**NIE czytaj plików prompt** — agent sam je przeczyta. Odpal **WSZYSTKICH** agentów naraz w jednym wywołaniu (jednym message z wieloma tool calls).

### 3. Zbierz wyniki

Po zakończeniu agentów, uruchom skrypt:

```bash
uv run python scripts/add_new_questions.py {instruction}
```

### 4. Wypisz podsumowanie

Wypisz ile pytań dodano i zachęć do przejrzenia:
```
Dodano X nowych pytań do weryfikacji.
Przejrzyj wyniki: make view ONLY={instruction}
```
