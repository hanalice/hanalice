# GitHub Profile Engineering - Local Preview Makefile

.PHONY: sync preview help

help:
	@echo "Usage:"
	@echo "  make sync     - Run sync script to update README.md"
	@echo "  make preview  - Alias for sync (updates content for preview)"

sync:
	python3 scripts/sync.py

preview: sync
	@echo "-----------------------------------------------------------"
	@echo "DONE: README.md has been regenerated from template."
	@echo "Next steps:"
	@echo "1. Open README.md in your IDE."
	@echo "2. Use the 'Markdown Preview' feature to see the result."
	@echo "3. Notice the rotated mascot and updated post list."
	@echo "-----------------------------------------------------------"
