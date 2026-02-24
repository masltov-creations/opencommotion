.PHONY: dev down test test-ui test-all test-e2e test-complete lint

dev:
	bash scripts/dev_up.sh

down:
	bash scripts/dev_down.sh

test:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) pytest -q -s --capture=no tests/unit tests/integration

test-ui:
	npm run ui:test

test-all: test test-ui

test-e2e:
	@bash -lc 'set -euo pipefail; make dev; trap "make down" EXIT; \
	for i in $$(seq 1 30); do \
		curl -fsS http://127.0.0.1:8000/health >/dev/null && curl -fsS http://127.0.0.1:8001/health >/dev/null && break; \
		sleep 1; \
	done; \
	npm run e2e'

test-complete: test-all test-e2e

lint:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) python -m py_compile services/gateway/app/main.py services/orchestrator/app/main.py
