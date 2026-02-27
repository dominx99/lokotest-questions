# Lokotest — quiz z instrukcji PKP

## Struktura projektu

```
instructions/{name}/
├── {name}.pdf                 # źródłowy PDF instrukcji
├── {name}.md                  # markdown (make pdfs-to-markdowns)
├── {name}-sections.json       # paragrafy (make sections)
├── {name}-pytania.xlsx        # pytania źródłowe
└── {name}-pytania.json        # pytania JSON (make xlsx-to-json)
```

## Pipeline

```
PDF → Markdown → sections.json
XLSX → pytania.json
```

Makefile targety: `pdfs-to-markdowns`, `sections`, `xlsx-to-json` (każdy przyjmuje opcjonalne `ONLY=Ir-1`).

## Weryfikacja pytań

Gdy użytkownik prosi o weryfikację pytań dla instrukcji — wczytaj prompt z `prompts/verify-questions.md` i postępuj według opisanej tam procedury.
