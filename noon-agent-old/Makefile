PYTHON ?= python3
VENV ?= .venv

.PHONY: install
install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e .[dev]

.PHONY: graph
graph:
	$(PYTHON) -m langgraph_cli.entrypoints.run --config langgraph.json
