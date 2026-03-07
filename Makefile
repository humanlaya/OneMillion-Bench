# Makefile for ExpertBench/omb

# Variables
PYTHON := python
PIP := pip
PYTEST := pytest
BLACK := black
ISORT := isort
FLAKE8 := flake8
MYPY := mypy
PYLINT := pylint
SRC_DIR := src
TEST_DIR := tests

.PHONY: help install test lint format clean check format-check

# Default target
help:
	@echo "Available commands:"
	@echo "  make install      - Install development dependencies"
	@echo "  make test         - Run tests using pytest"
	@echo "  make lint         - Run static analysis (flake8, mypy, pylint)"
	@echo "  make format       - Format code using black and isort"
	@echo "  make format-check - Check code formatting without modifying files"
	@echo "  make clean        - Remove build artifacts and cache directories"
	@echo "  make check        - Run all checks (format-check, lint, test)"

install:
	$(PIP) install -e ".[dev]"

test:
	@if [ -d "$(TEST_DIR)" ]; then \
		$(PYTEST); \
	else \
		echo "Warning: '$(TEST_DIR)' directory not found. Skipping tests."; \
	fi

lint:
	@echo "Running flake8..."
	-$(FLAKE8) $(SRC_DIR)
	@echo "Running mypy..."
	-$(MYPY) $(SRC_DIR)
	@echo "Running pylint..."
	-$(PYLINT) $(SRC_DIR)

format:
	@echo "Formatting with isort..."
	$(ISORT) $(SRC_DIR)
	@echo "Formatting with black..."
	$(BLACK) $(SRC_DIR)

format-check:
	@echo "Checking import sort order..."
	$(ISORT) --check-only --diff $(SRC_DIR)
	@echo "Checking code formatting..."
	$(BLACK) --check --diff $(SRC_DIR)

clean:
	rm -rf __pycache__
	rm -rf $(SRC_DIR)/__pycache__
	rm -rf $(SRC_DIR)/*/__pycache__
	rm -rf $(TEST_DIR)/__pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

check: format-check lint test
