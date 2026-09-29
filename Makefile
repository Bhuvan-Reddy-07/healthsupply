.PHONY: up down test test-phase0 test-phase1 simulate lint clean help demo check-env

help:
	@echo "Available commands:"
	@echo "  make check-env   - Verify Python 3.11 pinning in Docker and pyproject.toml"
	@echo "  make up          - Start all docker containers (postgres, nats, backend, dashboard)"
	@echo "  make down        - Stop all docker containers"
	@echo "  make simulate    - Run the synthetic 2-country data generator"
	@echo "  make test-phase0 - Run Phase 0 acceptance verification tests"
	@echo "  make test-phase1 - Run Phase 1 ingestion & edge tests"
	@echo "  make test        - Run full test suite"
	@echo "  make demo        - Run end-to-end demo"

check-env:
	python scripts/check_env.py

up:
	docker compose up -d postgres nats backend

down:
	docker compose down

simulate:
	python -m simulator.cli --generate --facilities 200 --items 150 --months 24

test-phase0:
	python -m pytest tests/ -v -s

test: test-phase0

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
