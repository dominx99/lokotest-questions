.PHONY: pdfs-to-markdowns pdf-to-markdown clean-markdowns sections section xlsx-to-json toc view apply-verification

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

# Generate table of contents from section frontmatters
# Usage: make toc              (all instructions)
#        make toc ONLY=Ir-1    (single instruction)
toc:
ifdef ONLY
	uv run python scripts/generate_toc.py --instructions-dir $(INSTRUCTIONS_DIR) --only $(ONLY)
else
	uv run python scripts/generate_toc.py --instructions-dir $(INSTRUCTIONS_DIR)
endif

# Open verification viewer in browser
# Usage: make view              (defaults to Ir-1)
#        make view ONLY=Ir-1
ONLY ?= Ir-1
view:
	@fuser -k 8080/tcp 2>/dev/null || true
	@xdg-open "http://localhost:8080/viewer/?name=$(ONLY)" 2>/dev/null || open "http://localhost:8080/viewer/?name=$(ONLY)" 2>/dev/null || true
	uv run python scripts/serve_viewer.py 8080

# Apply all verification fixes from CLI
# Usage: make apply-verification              (defaults to Ir-1)
#        make apply-verification ONLY=Ir-1
apply-verification:
	uv run python scripts/apply_verification.py $(ONLY)
