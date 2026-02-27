# Weryfikacja pytań quizowych

## Zadanie

Sprawdź pytania quizowe z pliku `{instruction}-pytania.json` pod kątem poprawności, porównując każde pytanie z treścią odpowiedniego paragrafu z pliku `{instruction}-sections.json`.

## Pliki

Oba pliki leżą w `instructions/{instruction}/`:

- **`{instruction}-pytania.json`** — pytania do sprawdzenia
- **`{instruction}-sections.json`** — treść paragrafów instrukcji

## Format danych

### pytania.json

```json
{
  "instruction": "Ir-1",
  "questions": [
    {
      "uuid": "5c982342-...",
      "question": "Kto może wydać zgodę na manewry?",
      "answers": { "A": "...", "B": "...", "C": "...", "D": "..." },
      "correct": "A",
      "explanation": "Ir-1 § 12 ust. 1",
      "section_ref": "§ 12"
    }
  ]
}
```

### sections.json

```json
{
  "instruction": "Ir-1",
  "sections": [
    {
      "id": "§ 12",
      "title": "Manewry na torach głównych",
      "chapter": "Rozdział 2. MANEWRY",
      "text": "1. Manewry na torach głównych mogą odbywać się tylko za zezwoleniem..."
    }
  ]
}
```

## Procedura

Dla każdego pytania:

1. Odczytaj `section_ref` z pytania (np. `§ 12`)
2. Znajdź sekcję o tym `id` w sections.json — wczytaj **tylko tę sekcję**, nie cały plik do kontekstu
3. Jeśli `section_ref` jest `null` — zanotuj to jako "brak referencji" i przejdź dalej
4. Sprawdź:
   - Czy **poprawna odpowiedź** (`correct`) faktycznie wynika z treści paragrafu?
   - Czy **pytanie** jest jednoznaczne i zrozumiałe?
   - Czy **błędne odpowiedzi** (distraktory) są wiarygodne ale faktycznie niepoprawne?
   - Czy `explanation` wskazuje właściwy ustęp?

## Format wyniku

Dla każdego pytania wypisz jednolinijkowy werdykt:

```
✓ Q1 (§ 12) — OK
✗ Q2 (§ 32) — Poprawna odpowiedź to B, nie C. § 32 ust. 1 mówi o 40 km/h.
? Q3 (brak ref) — Brak section_ref, nie można zweryfikować
⚠ Q4 (§ 58) — Pytanie niejednoznaczne: "rozkaz pisemny" może dotyczyć ust. 3 lub ust. 4
```

Na końcu podsumowanie:
```
Wynik: X/Y poprawnych, Z błędów, W bez referencji, V wątpliwych
```

## Ważne

- **NIE wczytuj całego sections.json do kontekstu** — plik ma ~680KB. Wczytaj go raz skryptem Pythona i wyciągaj po jednej sekcji.
- Przetwarzaj pytania **partiami** (np. po 10), żeby nie przekroczyć kontekstu.
- Jeśli sekcja jest bardzo długa (np. § 84 ma 120K chars), szukaj w niej konkretnego ustępu wskazanego w `explanation`.
