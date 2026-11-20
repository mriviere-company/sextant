# CLAUDE.md

Guidance for Claude Code in this repository. Working language with the author: French.

## What this is

Sextant is a multilingual RAG over the Area Universe game wiki, **built around its
evaluation**: every design choice is measured, compared and guarded by CI. It is a public
portfolio project; the README must stay readable in a minute by people and by AI screening
tools.

**`PLAN.md` (French) is the execution plan**: follow its phases in order and verify each
phase's acceptance criteria before moving on. A change of scope is written into the plan
before any code.

## Commands

`make help` lists everything. `make check` runs what CI runs (lint, mypy --strict, pytest,
corpus check). `make ingest` rebuilds `corpus/processed/`.

## Model and effort routing

Each phase in `PLAN.md` names the model and effort to use (Haiku 5.5 → Sonnet 5.5 →
Opus 5.5 → Fable 5.2). Run each step on its tier through subagents; escalate one tier when a
step resists (effort first, then model) and say so.

## Rules that do not bend

- **Evaluation integrity.** The test split of the evaluation set is never used to tune
  anything (prompts, thresholds, chunk size, `top_k`). Decision thresholds for a benchmark
  are written down before it runs.
- **Every published number links to a committed results file** (`eval/results/`,
  `corpus/processed/stats.json`). No figure in the README without its source.
- **Citations are verified in code**: an answer may only cite chunks it was given.
- **No secrets, no personal data in the repository.** API keys come from the environment
  (`.env`, git-ignored; GitHub secrets in CI). Player data from the game (phase 6) is
  aggregated and anonymized before anything is published (Québec Law 25).
- **Corpus ids are stable**: chunk ids derive from language, slug, section anchor and part,
  and sections are aligned across languages by position. Never renumber.

## Standards

- Python 3.12, `uv`, Pydantic v2 at every boundary, frozen models for data.
- mypy `--strict` and ruff must pass; tests next to every module change.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) that explain the why.
