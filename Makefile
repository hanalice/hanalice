# GitHub Profile Engineering - Local Preview Makefile

.PHONY: sync preview test help

help:
	@echo "Usage:"
	@echo "  make sync     - Run sync: README.md, tags/, and public/ (GitHub Pages)"
	@echo "  make preview  - Alias for sync (updates content for preview)"
	@echo "  make test     - Run unit tests"
	@echo ""
	@echo "After sync, open public/index.html or enable Pages from /public"
	@echo "(see docs/github-pages.md)."

sync:
	python3 scripts/sync.py

test:
	python3 -m unittest discover -s tests -v

preview: sync
	@echo "-----------------------------------------------------------"
	@echo "DONE: README.md and public/ have been regenerated."
	@echo "Next steps:"
	@echo "1. Open README.md in your IDE (Markdown Preview)."
	@echo "2. Or open public/index.html / serve public/ for the site."
	@echo "3. Notice the rotated mascot, post list, and static pages."
	@echo "-----------------------------------------------------------"
