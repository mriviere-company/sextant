# Retrieval benchmark protocol

Written on 2026-11-20, **before any benchmark run and before the evaluation set exists**.
Any change to this protocol is recorded in the change log at the bottom, with its reason,
before the run it affects.

## Data

- Evaluation set: `eval/dataset/questions.jsonl` (phase 1), each question validated by hand,
  with its relevant sections identified as `(slug, section_index)`. How it was built and its
  known biases: [`dataset/README.md`](dataset/README.md).
- The dev / test split is assigned to the candidates **before** the human review, by article
  (`eval/dataset/candidates.jsonl`), and never changes afterwards.
- **All decisions are made on the `dev` split.** The `test` split is run **once**, with the
  frozen configuration, at the end of phase 2; those are the figures published in the README.
- Unanswerable questions are excluded from retrieval metrics (no relevant section).
- **Cross-lingual questions** (asked in one language, searched in another language's wiki,
  field `corpus_lang`) are reported in their own table and **do not enter the decision
  metrics** below: `overall`, `by_lang` and the bootstrap comparisons are computed on
  monolingual questions only, the production case (a player searches the wiki in their own
  language).

## Metrics

- Relevance is judged per **section**: chunk hits are mapped to their section, a section
  keeps the rank of its best chunk.
- **Primary metric: nDCG@10.** Secondary: MRR, Recall@5, Hit@1. Latency p50 / p95 of one
  search, measured on the reference machine.
- Differences between strategies are tested with a **paired bootstrap** over questions
  (10 000 resamples, seed 42, 95 % interval). A difference is *significant* when the
  interval excludes zero.

## Strategies

| Spec | Role |
|---|---|
| `bm25` | Baseline: Okapi BM25 (k1 = 1.2, b = 0.75), Snowball stemming per language |
| `pg_fts` | PostgreSQL full text (`ts_rank_cd`, OR query): measured, not a production candidate by default |
| `dense:minilm` | paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions) |
| `dense:mpnet` | paraphrase-multilingual-mpnet-base-v2 (768) |
| `dense:e5-large` | multilingual-e5-large (1 024) |
| `hybrid:<model>` | RRF (k = 60) of `bm25` and the chosen dense model, top 50 of each |
| `rerank:bge-m3:<spec>` | bge-reranker-v2-m3 (int8) over the top 30 of the chosen first stage |
| `rerank:bge-m3@10:<spec>` | The same reranker over the top 10 only (cheaper variant) |

## Decision rules (fixed now)

1. **Dense model.** Rank dense models by nDCG@10. A larger model replaces a smaller one only
   if its gain is **≥ 0.02 nDCG@10 and significant**; otherwise the smaller, cheaper model
   is kept.
2. **Hybrid.** `hybrid:<model>` is adopted over the best single strategy only if its gain is
   **≥ 0.01 nDCG@10 and significant**; otherwise the simpler strategy is kept.
3. **Reranker.** Each variant (top 30, top 10) is adopted only if it adds **≥ 0.03 nDCG@10,
   significant**, and the complete search stays **≤ 500 ms at p95** on the reference machine.
   If both qualify, the cheaper one wins unless the other adds a further ≥ 0.02, significant.
4. **`pg_fts`** is adopted instead of `bm25` only under rule 2's threshold.
5. **No language left behind.** If the chosen configuration is worse than `bm25` by ≥ 0.05
   nDCG@10 in any language with at least 15 questions, that is reported as a finding and
   investigated before phase 3.

## Fixed parameters

Top 10 sections per query; chunks of at most 300 words with the article and section titles
prepended for embedding and BM25; HNSW cosine index with `ef_search = 200`; hybrid depth 50;
rerank depth 30, and 10 for the `@10` variant. Changing any of them is a protocol change.

## Reference machine

Latency figures come from the machine that runs the benchmark and are reported with it.
Initial reference: 4 vCPU, 15 GB RAM, no GPU, PostgreSQL 16 with pgvector 0.6.0 on the same
host.

## Change log

- 2026-11-20 — initial version.
- 2026-11-20 — added the `rerank:bge-m3@10` variant. Reason: a smoke test on three
  hand-written questions (not an evaluation; no quality was measured) took 4 to 9 s per
  query with 30 candidates on the reference machine, far above rule 3's 500 ms. Rule 3's
  thresholds are unchanged and apply to each variant; a tie-break is added: if both variants
  qualify, the cheaper one wins unless the other adds a further ≥ 0.02 nDCG@10, significant. Also observed: embedding the corpus with
  e5-large takes about 30 minutes on this machine (1.3 chunks/s).
- 2026-11-20 — before any run: cross-lingual questions (planned in phase 1) are searched in
  their `corpus_lang` and reported apart from the decision metrics, so that one population
  (monolingual questions) carries every decision; the dev / test split is frozen on the
  candidates before review. No benchmark had run.
