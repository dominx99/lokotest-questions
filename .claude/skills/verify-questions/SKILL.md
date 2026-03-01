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
  - **numer paragrafu** (np. `5` lub `12`) → `section_filter`
  - **`RESCUED`** (case-insensitive) → tryb RESCUED

Jeśli brak pierwszego argumentu, wypisz błąd: `Użycie: /verify-questions <instruction> [numer-paragrafu|RESCUED]` i zakończ.

## Procedura

### 1. Przygotuj batche

Uruchom skrypt, który pogrupuje pytania po sekcjach i wygeneruje prompty agentów:

**Bez filtra:**
```bash
uv run python scripts/prepare_verify_batches.py {instruction}
```

**Z filtrem sekcji:**
```bash
uv run python scripts/prepare_verify_batches.py {instruction} --section {section_filter}
```

**Tryb RESCUED:**
```bash
uv run python scripts/prepare_verify_batches.py {instruction} --rescued
```

Skrypt:
- Wczyta pytania (z pytania.json lub verification.json w trybie RESCUED)
- Pogrupuje po sekcjach, max 8 pytań per agent
- Wygeneruje gotowe prompty agentów w `/tmp/verify-{instruction}/prompt_*.md`
- Wypisze manifest JSON na stdout

Zapamiętaj manifest. Jeśli `total_questions == 0`, wypisz komunikat i zakończ.

### 2. Odpal agentów

Dla każdego batcha z manifestu (`batches`):
1. Wczytaj prompt z `prompt_path` (Read tool)
2. Odpal agenta z tym promptem:
   - model: **sonnet**
   - subagent_type: **general-purpose**
   - run_in_background: **true**

Odpal **WSZYSTKICH** agentów naraz w jednym wywołaniu (jednym message z wieloma tool calls).

### 3. Zbierz wyniki — uruchom skrypt merge

Po zakończeniu wszystkich agentów, uruchom skrypt:

**Tryb normalny:**
```bash
uv run python scripts/merge_verification.py {instruction}
```

**Tryb RESCUED:**
```bash
uv run python scripts/merge_verification.py {instruction} --rescued
```

Wypisz wynik skryptu jako podsumowanie i zachęć do przejrzenia:
```
Przejrzyj wyniki: make view ONLY={instruction}
```
