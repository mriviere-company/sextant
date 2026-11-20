.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install ingest check-corpus lint fmt typecheck test check db-up index bench-retrieval

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Install dependencies (uv)
	$(UV) sync

ingest: ## Build corpus/processed (chunks.jsonl, stats.json)
	$(UV) run python -m sextant.ingest

check-corpus: ## Fail if the committed corpus stats are stale
	$(UV) run python -m sextant.ingest --check

lint: ## ruff (lint + format check)
	$(UV) run ruff check src tests scripts
	$(UV) run ruff format --check src tests scripts

fmt: ## Format and auto-fix
	$(UV) run ruff format src tests scripts
	$(UV) run ruff check --fix src tests scripts

typecheck: ## mypy --strict
	$(UV) run mypy

test: ## pytest
	$(UV) run pytest

check: lint typecheck test check-corpus ## Everything CI runs

db-up: ## Start local PostgreSQL + pgvector (docker compose)
	docker compose up -d --wait

MODELS ?= minilm,mpnet,e5-large
index: ## Load chunks into PostgreSQL and embed them (MODELS=minilm,...)
	$(UV) run python -m sextant.retrieval.index --models $(MODELS)

SPLIT ?= dev
STRATEGIES ?= bm25,pg_fts,dense:minilm,dense:mpnet,dense:e5-large
bench-retrieval: ## Retrieval benchmark (SPLIT=dev|test STRATEGIES=...)
	$(UV) run python -m sextant.eval.retrieval_bench --split $(SPLIT) --strategies $(STRATEGIES)
