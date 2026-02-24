.PHONY: dev down test test-ui test-all lint

dev:
	bash scripts/dev_up.sh

down:
	bash scripts/dev_down.sh

test:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) pytest -q -s --capture=no tests/unit tests/integration

test-ui:
	npm run ui:test

test-all: test test-ui

lint:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) python -m py_compile services/gateway/app/main.py services/orchestrator/app/main.py
