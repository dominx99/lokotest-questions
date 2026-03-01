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

Jeśli brak pierwszego argumentu, wypisz błąd: `Użycie: /rescue-questions <instruction> [numer-paragrafu]` i zakończ.

## Procedura

### 1. Przygotuj batche

Uruchom skrypt, który wyekstrahuje kandydatów DELETE, pogrupuje je i wygeneruje prompty agentów:

**Bez filtra sekcji:**
```bash
uv run python scripts/prepare_rescue_batches.py {instruction}
```

**Z filtrem sekcji:**
```bash
uv run python scripts/prepare_rescue_batches.py {instruction} --section {section_filter}
```

Skrypt:
- Wyekstrahuje pytania DELETE z verification.json i pytania.json
- Pogrupuje po max 8 pytań w batch
- Wygeneruje gotowe prompty agentów w `/tmp/rescue-{instruction}/prompt_batch_N.md`
- Wypisze manifest JSON na stdout

Zapamiętaj manifest. Jeśli `total_candidates == 0`, wypisz komunikat i zakończ.

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

```bash
uv run python scripts/merge_rescue.py {instruction}
```

Skrypt:
- Wczyta wszystkie pliki JSON z `/tmp/rescue-{instruction}/`
- Zaktualizuje `{instruction}-verification.json`: zmieni status DELETE→RESCUED z `changes`, lub zostawi potwierdzone DELETE
- Przeliczy `summary` (z polem `rescued`)
- Wypisze podsumowanie

Wypisz wynik skryptu jako podsumowanie.
