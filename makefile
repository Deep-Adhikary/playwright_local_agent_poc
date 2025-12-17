# -----------------------------
# Config
# -----------------------------
PYTHON_VERSION := 3.11.14
VENV_DIR := .venv
LOCKFILE := uv.lock
PYPROJECT := pyproject.toml

# -----------------------------
# Default target
# -----------------------------
.DEFAULT_GOAL := help

# -----------------------------
# Targets
# -----------------------------

help:
	@echo ""
	@echo "Available targets:"
	@echo "  make init        -> setup python, venv, and install deps"
	@echo "  make venv        -> create virtual environment"
	@echo "  make compile     -> resolve & lock dependencies (uv.lock)"
	@echo "  make sync        -> sync venv to lockfile"
	@echo "  make install     -> compile + sync"
	@echo "  make update      -> update lockfile with latest compatible deps"
	@echo "  make clean       -> remove virtual environment and lockfile"
	@echo ""

# -----------------------------
# Environment setup
# -----------------------------

init: venv install

venv:
	@echo ">> Using Python $(PYTHON_VERSION)"
	@pyenv install -s $(PYTHON_VERSION)
	@pyenv local $(PYTHON_VERSION)
	@uv venv $(VENV_DIR)

# -----------------------------
# Dependency management
# -----------------------------

compile:
	@echo ">> Compiling dependencies"
	@uv pip compile $(PYPROJECT) -o $(LOCKFILE)

sync:
	@echo ">> Syncing environment"
	@uv pip sync $(LOCKFILE)

install: compile sync

update:
	@echo ">> Updating dependencies"
	@uv pip compile --upgrade $(PYPROJECT) -o $(LOCKFILE)
	@uv pip sync $(LOCKFILE)

compile-dev:
	@uv pip compile pyproject.toml --extra dev -o uv.lock

install-dev: compile-dev sync

update-dev:
	@echo ">> Updating prod + dev dependencies"
	@uv pip compile --upgrade $(PYPROJECT) --extra dev -o $(LOCKFILE)
	@uv pip sync $(LOCKFILE)

# -----------------------------
# Linting
# -----------------------------#
lint:
	@ruff check .

fmt:
	@ruff format .

typecheck:
	@mypy .

check: lint typecheck
# -----------------------------
# Cleanup
# -----------------------------

clean:
	@echo ">> Cleaning environment"
	@rm -rf $(VENV_DIR) $(LOCKFILE)
