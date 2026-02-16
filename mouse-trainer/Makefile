.PHONY: install run lint format check clean help

# Default target
.DEFAULT_GOAL := help

# Python source files
PYTHON_FILES := mouse_trainer.py

# Use uv for dependency management
# uv is configured with python-preference = "system" in pyproject.toml
# to use system Python which has tkinter
# Using explicit path to avoid pyenv shim conflicts
UV := $(HOME)/.local/bin/uv

help: ## Show this help message
	@echo "Mouse Trainer - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	@echo "Installing Python dependencies..."
	$(UV) sync
	@echo ""
	@echo "Verifying tkinter..."
	@$(UV) run python -c "import tkinter" && echo "✓ tkinter is available" || echo "✗ Install tkinter: sudo apt install python3-tk"

run: ## Run the mouse trainer application
	$(UV) run python mouse_trainer.py

lint: ## Run ruff linter (shows issues, doesn't fail)
	-$(UV) run ruff check $(PYTHON_FILES)

lint-strict: ## Run ruff linter (fails on issues)
	$(UV) run ruff check $(PYTHON_FILES)

lint-fix: ## Run ruff linter with auto-fix
	$(UV) run ruff check --fix $(PYTHON_FILES)

format: ## Format code with ruff
	$(UV) run ruff format $(PYTHON_FILES)

format-check: ## Check code formatting (shows issues, doesn't fail)
	-$(UV) run ruff format --check $(PYTHON_FILES)

check: lint format-check ## Run all checks (lint + format check)

check-strict: lint-strict ## Run strict checks (fails on issues)
	$(UV) run ruff format --check $(PYTHON_FILES)

fix: lint-fix format ## Fix all issues (lint fix + format)

clean: ## Clean generated files
	rm -rf __pycache__
	rm -rf .ruff_cache
	rm -rf *.egg-info
	rm -rf dist
	rm -rf build
	rm -f round_times.log
