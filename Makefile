.PHONY: install run dev down setup-wizard test test-ui test-all test-e2e security-checks perf-checks test-complete lint fresh-agent-e2e voice-preflight

install:
	bash scripts/install_local.sh

run:
	bash scripts/dev_up.sh --ui-mode dist

dev:
	bash scripts/dev_up.sh --ui-mode dev

down:
	bash scripts/dev_down.sh

setup-wizard:
	python3 scripts/setup_wizard.py

test:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) pytest -q -s --capture=no tests/unit tests/integration

test-ui:
	npm run ui:test

test-all: test test-ui

test-e2e:
	@bash -lc 'set -euo pipefail; make dev; trap "make down" EXIT; \
	PW_LIB_DIR="$$(bash scripts/ensure_playwright_libs.sh)"; \
	for i in $$(seq 1 30); do \
		curl -fsS http://127.0.0.1:8000/health >/dev/null && curl -fsS http://127.0.0.1:8001/health >/dev/null && break; \
		sleep 1; \
	done; \
	LD_LIBRARY_PATH="$$PW_LIB_DIR:$${LD_LIBRARY_PATH:-}" npm run e2e'

security-checks:
	. .venv/bin/activate && python -m pip check
	. .venv/bin/activate && python -m pip install -q pip-audit
	. .venv/bin/activate && pip-audit -r requirements.txt --no-deps --disable-pip --progress-spinner off --timeout 10
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) pytest -q -s --capture=no tests/integration/test_security_baseline.py
	npm audit --audit-level=high

perf-checks:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) pytest -q -s --capture=no tests/integration/test_performance_thresholds.py
	npm --workspace @opencommotion/ui run test -- src/runtime/sceneRuntime.test.ts

test-complete: test-all test-e2e security-checks perf-checks

lint:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) python -m py_compile services/gateway/app/main.py services/orchestrator/app/main.py

fresh-agent-e2e:
	bash scripts/fresh_agent_consumer_e2e.sh

voice-preflight:
	. .venv/bin/activate && PYTHONPATH=$(CURDIR) python scripts/voice_preflight.py
