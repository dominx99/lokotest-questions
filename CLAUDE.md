# Lokotest — quiz z instrukcji PKP

## Struktura projektu

```
instructions/{name}/
├── {name}.pdf                 # źródłowy PDF instrukcji
├── {name}.md                  # markdown (make pdfs-to-markdowns)
├── sections/                  # paragrafy (make sections)
│   ├── §1.md
│   ├── §2.md
│   └── ...
├── {name}-pytania.xlsx        # pytania źródłowe
└── {name}-pytania.json        # pytania JSON (make xlsx-to-json)
```

## Pipeline

```
PDF → Markdown → sections/*.md
XLSX → pytania.json
```

Makefile targety: `pdfs-to-markdowns`, `sections`, `xlsx-to-json` (każdy przyjmuje opcjonalne `ONLY=Ir-1`).

## Weryfikacja pytań

Weryfikacja pytań: `/verify-questions {name}`

Podgląd wyników weryfikacji: `make view ONLY=Ir-1`

## Zasady

- Do usuwania plików używaj `trash` zamiast `rm`.
