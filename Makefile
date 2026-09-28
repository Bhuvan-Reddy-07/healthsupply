.PHONY: up down test test-phase0 simulate lint clean help demo

help:
	@echo "Available commands:"
	@echo "  make up          - Start all docker containers (postgres, nats, backend, dashboard)"
	@echo "  make down        - Stop all docker containers"
	@echo "  make simulate    - Run the synthetic 2-country data generator"
	@echo "  make test-phase0 - Run Phase 0 acceptance verification tests"
	@echo "  make test        - Run full test suite"
	@echo "  make demo        - Run end-to-end demo"

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
