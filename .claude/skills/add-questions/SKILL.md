---
name: add-questions
description: Generowanie brakujących pytań quizowych dla paragrafów instrukcji
disable-model-invocation: true
user-invocable: true
argument-hint: [nazwa-instrukcji] [numer-paragrafu]
---

# Generowanie brakujących pytań

Generuj nowe pytania quizowe dla paragrafów instrukcji, które mają zbyt mało pytań. Nowe pytania trafiają do pipeline weryfikacji ze statusem **NEW**.

## Parsowanie argumentów

Rozparsuj `$ARGUMENTS` na:
- **instruction** — pierwszy argument (wymagany), np. `Ir-1`
- **section_filter** — drugi argument (opcjonalny), sam numer paragrafu, np. `5` lub `12`

Jeśli `section_filter` podano, generuj pytania **tylko** dla tej sekcji.

## Procedura

### 1. Wczytaj pytania i policz per sekcja

Wczytaj `instructions/{instruction}/{instruction}-pytania.json`. Policz pytania per `section_ref`.

### 2. Oblicz deficyt pytań per sekcja

Dla każdego pliku sekcji w `instructions/{instruction}/sections/`:
- Policz liczbę linii w pliku (użyj Read tool)
- `wymagane = max(1, lines // 20)`
- `istniejące` = liczba pytań z pasującym `section_ref`
- `deficyt = wymagane - istniejące`

Pomiń sekcje z `deficyt <= 0`.

Pomiń plik `_attachments.md` (to nie jest sekcja).

Jeśli podano `section_filter`, filtruj do pasującej sekcji (np. `5` → `§5.md`).

Wypisz tabelę podsumowującą:
```
Sekcja   | Linii | Wymagane | Istniejące | Deficyt | Do dodania
§ 1      | 45    | 2        | 0          | 2       | 2
§ 5      | 120   | 6        | 2          | 4       | 4
...
Razem: X pytań do wygenerowania
```

### 3. Utwórz katalog na wyniki

```bash
mkdir -p /tmp/add-questions-{instruction}
```

Wyczyść wcześniejsze pliki:
```bash
rm -f /tmp/add-questions-{instruction}/*.json
```

### 4. Odpal agentów — 1 per sekcja

`do_dodania = min(deficyt, 10)` per sekcja.

Uruchom **wszystkich** agentów w jednym wywołaniu (jednym message z wieloma tool calls). Każdy agent:
- model: **sonnet**
- subagent_type: **general-purpose**
- run_in_background: **true**

Po odpaleniu wszystkich, czekaj na ich zakończenie.

#### Prompt dla agenta

```
Jesteś generatorem pytań quizowych z instrukcji kolejowej {instruction} (PKP).

## Zadanie

1. Przeczytaj plik sekcji: instructions/{instruction}/sections/{section_file}
2. Wygeneruj {do_dodania} nowych pytań quizowych na podstawie treści sekcji
3. Zapisz wyniki do pliku: /tmp/add-questions-{instruction}/{section_ref}.json

## Istniejące pytania z tej sekcji (NIE DUPLIKUJ)

{existing_questions_json}

## Wymagania dla pytań

1. Każde pytanie musi mieć **dokładnie 4 odpowiedzi** (A, B, C, D)
2. Dokładnie **jedna** odpowiedź jest poprawna
3. Pytanie musi wynikać **bezpośrednio** z treści paragrafu — nie wymyślaj faktów
4. Dystraktory (błędne odpowiedzi) muszą być wiarygodne ale faktycznie niepoprawne
5. Pytanie powinno być jednoznaczne, precyzyjne i poprawne językowo (po polsku)
6. `explanation` musi zawierać **wyłącznie** referencję do paragrafu w formacie: `{instruction} § X ust. Y` (opcjonalnie pkt, litera, tabela)
7. Każde pytanie musi mieć unikalny UUID (wygeneruj za pomocą pythona: `import uuid; str(uuid.uuid4())`)
8. `section_ref` = "{section_ref}"

## Format wyjścia — ZAPISZ DO PLIKU

Użyj Write tool aby zapisać listę pytań jako JSON:

[
  {{
    "uuid": "<nowy uuid>",
    "question": "Treść pytania?",
    "answers": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "A",
    "explanation": "{instruction} § X ust. Y",
    "section_ref": "{section_ref}"
  }}
]

WAŻNE: Musisz użyć Write tool aby zapisać plik JSON. To jest Twoje główne zadanie.
```

### 5. Zbierz wyniki

Po zakończeniu agentów, uruchom skrypt:

```bash
uv run python scripts/add_new_questions.py {instruction}
```

### 6. Wypisz podsumowanie

Wypisz ile pytań dodano do weryfikacji i zachęć do przejrzenia:
```
Dodano X nowych pytań do weryfikacji.
Przejrzyj wyniki: make view ONLY={instruction}
```
