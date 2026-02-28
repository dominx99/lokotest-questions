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

### 2. Pogrupuj pytania po section_ref

Pogrupuj pytania po wartości `section_ref`. Pytania bez `section_ref` (null) umieść w osobnej grupie "brak_ref".

### 3. Odpal agentów równolegle

Uruchom agentów (subagent_type: "general-purpose") — po jednym na grupę sekcji (lub kilka małych sekcji w jednej grupie, max ~15 agentów). Każdy agent:

- Czyta pliki sekcji z `instructions/$ARGUMENTS/sections/§X.md` (dla każdego unikalnego section_ref w swojej grupie)
- Dla każdego pytania sprawdza:
  - Czy **poprawna odpowiedź** (`correct`) faktycznie wynika z treści paragrafu?
  - Czy **pytanie** jest jednoznaczne, precyzyjne i poprawne językowo (polska gramatyka)?
  - Czy **błędne odpowiedzi** (dystraktory) są wiarygodne ale faktycznie niepoprawne?
  - Czy `explanation` wskazuje właściwy paragraf, ustęp i podpunkt (jeśli jest w danym ustępie)?
  - Czy nie ma literówek, powtórzeń, nielogicznych sformułowań, nadmiarowych słów których nie ma w danym paragrafie/ustępie?
- Zwraca **szczegółowy** werdykt per pytanie w formacie:

```
## Q{index} ({uuid}) — OK|FIX|DELETE

**Pytanie**: {question}
**Odpowiedź**: {correct}: {answer_text}
**Referencja**: {explanation}

### Problemy:
- {opis problemu 1}
- {opis problemu 2}

### Sugerowane zmiany (tylko dla FIX):
- question: "nowa treść pytania"
- answers.A: "nowa odpowiedź A"
- correct: "B"
- explanation: "Ir-1 § X ust. Y"
```

Prompt dla każdego agenta powinien zawierać:
- Pełną treść pytań z jego grupy (wklejone w prompt, nie "przeczytaj plik")
- Ścieżki do plików sekcji do przeczytania
- Instrukcję zwrócenia werdyktu w powyższym formacie
- Uwagę: "Bądź dokładny i szczegółowy. Nie kompresuj werdyktu do jednej linijki."

### 4. Zbierz wyniki

Po zakończeniu wszystkich agentów, zbierz wyniki. Sparsuj werdykty i utwórz raport JSON:

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

### 5. Zapisz raport

Zapisz raport do `instructions/$ARGUMENTS/$ARGUMENTS-verification.json`.

Wypisz podsumowanie:
```
Weryfikacja $ARGUMENTS: X pytań OK, Y do poprawy, Z do usunięcia
```

### 6. Zapytaj użytkownika

Użyj AskUserQuestion aby zapytać:
- "Czy zastosować poprawki (FIX/DELETE) na pytaniach?" z opcjami:
  - "Tak, zastosuj wszystkie" — zastosuj FIX i DELETE
  - "Pokaż szczegóły najpierw" — wypisz wszystkie FIX i DELETE ze szczegółami
  - "Nie, tylko zapisz raport" — zakończ

### 7. Zastosuj poprawki (jeśli użytkownik potwierdzi)

Wczytaj `instructions/$ARGUMENTS/$ARGUMENTS-pytania.json`. Dla każdego wyniku:
- **FIX**: zastosuj zmiany z `changes` na odpowiednim pytaniu (dopasowanie po `uuid`)
- **DELETE**: usuń pytanie z listy

Zapisz zaktualizowany plik. Wypisz:
```
Zastosowano: X poprawek, Y usunięć. Pozostało Z pytań.
```
