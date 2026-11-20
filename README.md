# Sextant

[![CI](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml/badge.svg)](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml)

A multilingual RAG over the [Area Universe](https://www.areauniverse.com/) game wiki, built
around its evaluation: players ask a question in their language and get an answer that cites
the wiki sections it comes from, and every design choice (chunking, lexical, vector or hybrid
retrieval, reranking, model, prompt) is measured, compared and guarded by CI.

**Status: work in progress — phase 0 of 7 (foundations) done.** The full plan, with
acceptance criteria per phase, is in [`PLAN.md`](PLAN.md) (French).

## The corpus

The official game wiki: **72 articles in 6 languages** (French, English, German, Spanish,
Portuguese, Russian), each split on its `<h2>` sections so that a citation links straight to
`areauniverse.com/wiki/<slug>#<section>`. Section anchors are translated, but every article
has the same section layout in all six languages, so one passage can be referenced across
languages — the basis for cross-lingual evaluation. Figures:
[`corpus/processed/stats.json`](corpus/processed/stats.json).

## What is done (phase 0)

- Snapshot of the wiki with its source revision ([`corpus/`](corpus/README.md)).
- Ingestion: YAML → typed articles → `<h2>` sections → chunks with stable ids
  (`fr:first_fleet#composer:0`), citation URLs and a contextual header for embedding.
- HTML → light Markdown conversion (lists, tables with headers), tested word-for-word
  lossless on the whole corpus in all six languages.
- Strict typing (mypy `--strict`), ruff, pytest, and CI that fails if the published corpus
  figures drift from the data.

## Run it

```bash
uv sync
make ingest   # writes corpus/processed/chunks.jsonl and stats.json
make check    # lint, types, tests, corpus check
```

## Next

Phase 1 builds the evaluation set (questions validated by hand, unanswerable and
cross-lingual questions); phase 2 benchmarks BM25, vector, hybrid and reranked retrieval
(recall@k, MRR, nDCG). See [`PLAN.md`](PLAN.md).

## License

Code: [MIT](LICENSE). Wiki content in `corpus/`: © Area Universe, all rights reserved,
included for research and evaluation; see [`corpus/README.md`](corpus/README.md).
