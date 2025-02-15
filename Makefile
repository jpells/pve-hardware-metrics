# Colors for better visibility
BLUE := \033[36m
NC := \033[0m  # No Color

.PHONY: install
install: ## Install the app and pre-commit hooks with uv
	@echo "🎉 Installing the app and pre-commit hooks with uv..."
	@uv sync
	@uv run pre-commit install
	@uv run pre-commit install --hook-type commit-msg

.PHONY: check
check: ## Run code quality checks (pre-commit hooks and mypy)
	@echo "🚑 Verifying uv lock file..."
	@uv lock --locked
	@echo "🚑 Running pre-commit hooks..."
	@uv run pre-commit run -a
	@echo "🚑 Running mypy type checker..."
	@uv run mypy

.PHONY: test
test: ## Run tests with pytest and coverage
	@echo "🚨 Running pytest with coverage..."
	@uv run python -m pytest --cov --cov-config=pyproject.toml

.PHONY: help
help: ## Display available commands with descriptions
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  ${BLUE}%-15s${NC} %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""

# Default target when running just 'make'
.DEFAULT_GOAL := help
