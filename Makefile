.PHONY: pdfs-to-markdowns clean-markdowns

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
