# Sextant

[![CI](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml/badge.svg)](https://github.com/mriviere-company/sextant/actions/workflows/ci.yml)

A multilingual RAG over the [Area Universe](https://www.areauniverse.com/) game wiki, built
around its evaluation: players ask a question in their language and get an answer that cites
the wiki sections it comes from, and every design choice (chunking, lexical, vector or hybrid
retrieval, reranking, model, prompt) is measured, compared and guarded by CI.

**Status: work in progress.** Phases 0 to 2 are done: the corpus is ingested, the
evaluation set holds 158 questions validated by hand in six languages, and the retrieval
benchmark has chosen its configuration on dev and been run once on test. Generation (phase 3)
is next. The full plan, with acceptance criteria per phase, is in [`PLAN.md`](PLAN.md) (French).

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

## The evaluation set (phase 1)

- **288 candidate questions**, 48 per language: factual, procedural, comparative,
  multi-section (half of them spanning two linked articles) and **42 unanswerable** ones
  (14.6 %) to measure refusal; **24 cross-lingual** questions (asked in one language,
  searched in another language's wiki).
- Drafted by an LLM from each article, then **written natively in each language** from that
  language's wiki, in three player styles (search-box query, sentence, "I have… can I…").
- **Relevance completed by pooling**: every question is searched with all five retrieval
  strategies and an LLM judge marks which pooled sections answer it, so retrieval is not
  penalized for finding the same fact in another article.
- **Split frozen before review**, by article, balanced by language × kind; a mobile review
  page lets the game's author keep, correct or reject each question, its reference answer
  and its sections.
- **Validated:** 159 candidates reviewed, **158 validated** (84 dev, 74 test), 22 unanswerable,
  13 cross-lingual ([`eval/dataset/stats.json`](eval/dataset/stats.json)). Relevance labels
  were not changed by the reviewer, and per-language dev samples are small (9 to 12
  monolingual answerable questions): both are stated as limits, not hidden.
- Method, review outcome and known biases: [`eval/dataset/README.md`](eval/dataset/README.md).

## Retrieval benchmark (phase 2)

Test split, 57 monolingual questions, run once after the configuration was chosen and
committed on dev. Source: [`eval/results/retrieval_test.md`](eval/results/retrieval_test.md);
decision: [`eval/results/retrieval_decision.md`](eval/results/retrieval_decision.md).

| Strategy | nDCG@10 | vs BM25 (95 % CI) | p95 latency |
|---|---|---|---|
| BM25 (baseline) | 0.792 | — | 2 ms |
| PostgreSQL full text | 0.425 | −0.367 [−0.456, −0.280] | 26 ms |
| **dense multilingual-e5-large (chosen on dev)** | **0.839** | +0.046 [−0.019, +0.117] | 656 ms |
| hybrid e5-large + BM25 (RRF) | 0.865 | +0.073 [+0.034, +0.115] | 116 ms |
| + bge-reranker-v2-m3 over the top 10 | 0.886 | +0.094 [+0.033, +0.160] | 4.9 s |

What the numbers say, without spin ([full report](eval/results/README.md)): the dense model
leads BM25 but not significantly on 57 questions; the hybrid's extra gain over it is not
significant on either split, so the simpler configuration was kept; reranking helps
reproducibly (+0.05 nDCG@10 on dev and test) but costs seconds per query on 4 vCPUs; BM25 is
strong because generated questions reuse the wiki's words, a bias stated with the dataset.

How it is built:

- Retrieval strategies behind one interface: hand-written **BM25** (Snowball stemming per
  language), **PostgreSQL full text**, **dense** search with three local multilingual
  embedding models in **pgvector** (HNSW), **hybrid** fusion (RRF) and **cross-encoder
  reranking** (bge-reranker-v2-m3).
- Section-level metrics (hit@k, recall@k, precision@k, MRR, nDCG@10) per language and per
  question type, with a **paired bootstrap** to tell real differences from noise.
- Decision rules written **before** any run ([`eval/PROTOCOL.md`](eval/PROTOCOL.md)) and
  applied by code (`sextant.eval.retrieval_decision`), committed before the test run.

## Run it

```bash
uv sync
make ingest            # corpus/processed/chunks.jsonl and stats.json
make check             # lint, types, tests, corpus check
make db-up             # PostgreSQL + pgvector (docker compose)
make index             # load and embed the corpus (MODELS=minilm,mpnet,e5-large)
make candidates        # regenerate the candidates (replays the LLM cache; DEEPSEEK_API_KEY)
make review-page       # data of the review page (eval/review/)
make dataset           # questions.jsonl and stats.json from the reviews
make bench-retrieval   # once eval/dataset/questions.jsonl exists
```

## Next

Generation and API (phase 3): answers that cite only the sections they were given, and
refuse when the wiki has no answer. See [`PLAN.md`](PLAN.md).

## License

Code: [MIT](LICENSE). Wiki content in `corpus/`: © Area Universe, all rights reserved,
included for research and evaluation; see [`corpus/README.md`](corpus/README.md).
