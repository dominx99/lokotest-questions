.PHONY: pdfs-to-markdowns pdf-to-markdown clean-markdowns sections section xlsx-to-json view

INSTRUCTIONS_DIR := instructions

# Convert all PDFs in instructions/*/ to Markdown
pdfs-to-markdowns:
	uv run python scripts/pdf_to_markdown.py --instructions-dir $(INSTRUCTIONS_DIR)

# Convert a single instruction: make pdf-to-markdown ONLY=Ir-1
pdf-to-markdown:
	uv run python scripts/pdf_to_markdown.py --instructions-dir $(INSTRUCTIONS_DIR) --only $(ONLY)

# Remove all generated .md files from instruction directories
clean-markdowns:
	find $(INSTRUCTIONS_DIR) -name "*.md" -delete

# Split markdowns into per-section .md files
# Usage: make sections              (all instructions)
#        make section ONLY=Ir-1     (single instruction)
sections:
	uv run python scripts/md_to_sections.py --instructions-dir $(INSTRUCTIONS_DIR)

section:
	uv run python scripts/md_to_sections.py --instructions-dir $(INSTRUCTIONS_DIR) --only $(ONLY)

# Convert XLSX question files to JSON
# Usage: make xlsx-to-json              (all instructions)
#        make xlsx-to-json ONLY=Ir-1    (single instruction)
xlsx-to-json:
ifdef ONLY
	uv run python scripts/xlsx_to_json.py --instructions-dir $(INSTRUCTIONS_DIR) --only $(ONLY)
else
	uv run python scripts/xlsx_to_json.py --instructions-dir $(INSTRUCTIONS_DIR)
endif

# Open verification viewer in browser
# Usage: make view              (defaults to Ir-1)
#        make view ONLY=Ir-1
ONLY ?= Ir-1
view:
	@python3 -m http.server 8080 -d . &
	@sleep 0.3
	@xdg-open "http://localhost:8080/viewer/?name=$(ONLY)" 2>/dev/null || open "http://localhost:8080/viewer/?name=$(ONLY)" 2>/dev/null || echo "Open http://localhost:8080/viewer/?name=$(ONLY)"
	@echo "Server running on http://localhost:8080 — Ctrl+C to stop"
	@wait
