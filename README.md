# Sextant

[![CI](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml/badge.svg)](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml)

A multilingual RAG over the [Area Universe](https://www.areauniverse.com/) game wiki, built
around its evaluation: players ask a question in their language and get an answer that cites
the wiki sections it comes from, and every design choice (chunking, lexical, vector or hybrid
retrieval, reranking, model, prompt) is measured, compared and guarded by CI.

**Status: work in progress.** Phase 0 is done and the phase 2 tooling is ready; the
retrieval benchmark runs as soon as the phase 1 evaluation set exists. The full plan, with
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

## What is ready for the benchmark (phase 2 tooling)

- Retrieval strategies behind one interface: hand-written **BM25** (Snowball stemming per
  language), **PostgreSQL full text**, **dense** search with three local multilingual
  embedding models in **pgvector** (HNSW), **hybrid** fusion (RRF) and **cross-encoder
  reranking** (bge-reranker-v2-m3).
- Section-level metrics (hit@k, recall@k, precision@k, MRR, nDCG@10) per language and per
  question type, with a **paired bootstrap** to tell real differences from noise.
- Decision rules written **before** any run: [`eval/PROTOCOL.md`](eval/PROTOCOL.md).

## Run it

```bash
uv sync
make ingest            # corpus/processed/chunks.jsonl and stats.json
make check             # lint, types, tests, corpus check
make db-up             # PostgreSQL + pgvector (docker compose)
make index             # load and embed the corpus (MODELS=minilm,mpnet,e5-large)
make bench-retrieval   # once eval/dataset/questions.jsonl exists
```

## Next

Phase 1 builds the evaluation set (questions validated by hand, including unanswerable
ones); the retrieval benchmark then runs on it. See [`PLAN.md`](PLAN.md).

## License

Code: [MIT](LICENSE). Wiki content in `corpus/`: © Area Universe, all rights reserved,
included for research and evaluation; see [`corpus/README.md`](corpus/README.md).
