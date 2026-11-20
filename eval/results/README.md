# Retrieval benchmark (phase 2)

Rules fixed before any run: [`../PROTOCOL.md`](../PROTOCOL.md) (its change log records how the
rules are read and how latency is measured). Evaluation set: [`../dataset/`](../dataset/README.md),
158 questions validated by hand. Machine: 4 vCPU, 15 GB RAM, no GPU, PostgreSQL 16 with
pgvector 0.6.0 on the same host.

| File | What it holds |
|---|---|
| `retrieval_dev_1_first_stage.*`, `retrieval_dev_2_hybrid.*`, `retrieval_dev_3_rerank.*` | Dev runs, in the order the rules asked for them |
| `retrieval_decision.*` | The rules applied by code (`sextant.eval.retrieval_decision`) to the dev runs |
| `dev_latency_checks/` | Latency re-measurements after an anomaly in the first dev run |
| `retrieval_test.*` | The single test run, one process per strategy, merged |

## Decision on dev

Dev split: 84 questions, 66 of them monolingual and answerable (the population every rule
uses). Applied by code, committed before the test run:

| Rule | Comparison | Δ nDCG@10 | 95 % CI | Outcome |
|---|---|---|---|---|
| 1 | MiniLM → mpnet | −0.110 | [−0.175, −0.048] | MiniLM kept |
| 1 | MiniLM → e5-large | +0.138 | [+0.076, +0.202] | **e5-large adopted** |
| 4 | BM25 → PostgreSQL full text | −0.302 | [−0.379, −0.225] | BM25 kept |
| 2 | e5-large → hybrid (RRF with BM25) | +0.011 | [−0.023, +0.044] | not significant, e5-large kept |
| 3 | e5-large → rerank top 30 | +0.086 | [+0.050, +0.124] | gain, but 14.4 s at p95 |
| 3 | e5-large → rerank top 10 | +0.048 | [+0.022, +0.079] | gain, but 4.1 s at p95 (4.7 s re-measured) |

**Chosen configuration: `dense:e5-large`.** Rule 5 could not apply: no language has the
15 dev questions it needs. Source: [`retrieval_decision.md`](retrieval_decision.md).

## Test, run once

57 monolingual answerable questions. Source: [`retrieval_test.md`](retrieval_test.md).

| Strategy | nDCG@10 | MRR | Recall@5 | Hit@1 | Δ nDCG@10 vs BM25 (95 % CI) | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| BM25 | 0.792 | 0.841 | 0.785 | 0.772 | — | 1.5 | 2.4 |
| PostgreSQL full text | 0.425 | 0.436 | 0.407 | 0.298 | −0.367 [−0.456, −0.280] | 18.5 | 25.8 |
| dense MiniLM | 0.552 | 0.600 | 0.565 | 0.491 | −0.240 [−0.342, −0.140] | 31.7 | 45.9 |
| dense mpnet | 0.604 | 0.669 | 0.585 | 0.561 | −0.189 [−0.291, −0.090] | 47.6 | 59.8 |
| **dense e5-large (chosen)** | **0.839** | 0.896 | 0.808 | 0.825 | +0.046 [−0.019, +0.117] | 221.4 | 655.8 |
| hybrid e5-large + BM25 | 0.865 | 0.917 | 0.827 | 0.877 | +0.073 [+0.034, +0.115] | 81.8 | 116.2 |
| rerank top 10 over e5-large | 0.886 | 0.959 | 0.843 | 0.947 | +0.094 [+0.033, +0.160] | 2 125 | 4 919 |
| rerank top 30 over e5-large | 0.891 | 0.958 | 0.845 | 0.947 | +0.099 [+0.041, +0.163] | 9 312 | 16 527 |

## Findings

1. **The chosen configuration is not significantly better than BM25 on test** (+0.046, CI
   crosses zero; on dev the lower bound was +0.001). With 57 questions, the dense model's
   lead over BM25 is real on average but not established.
2. **Hybrid versus e5-large is unresolved on both splits** (+0.011 on dev, +0.027 on test,
   neither significant), so the dev decision stands. On test the hybrid is the only first
   stage significantly above BM25. A larger dev split (129 candidates are still unreviewed)
   is the way to settle it; the test split cannot.
3. **Reranking helps, reproducibly, but not at this price.** The top-10 variant adds +0.048
   on dev and +0.047 on test over e5-large (both significant), at 2.1 s median and 4.9 s
   p95 on 4 vCPUs, ten times the 500 ms budget. It needs a GPU or a smaller cross-encoder.
4. **BM25 is a strong baseline here**, partly because the questions were drafted from the
   sections they target and reuse their words ([known biases](../dataset/README.md#known-biases)).
   Real player questions (phase 6) should widen the gap in favor of dense retrieval.
5. **Cross-lingual questions** (5 in dev, 8 in test): BM25 collapses (0.125 nDCG@10 on test),
   e5-large holds (0.782). Expected, but the sample is anecdotal.
6. **The two small dense models swap places** between dev and test (MiniLM ahead on dev,
   mpnet on test); both are far below e5-large and BM25. Small samples, not a model finding.
7. **PostgreSQL full text** (OR query ranked by `ts_rank_cd`, no IDF) is far below BM25, as
   expected; it stays out.
8. **Latency.** The e5-large query embedding dominates and is unstable on this CPU: its p50
   ranged from 99 to 440 ms across runs, while the hybrid, which computes the same
   embedding, stayed at 80–90 ms; the cause is open. The database part is an exact scan of
   about 3 ms: at this corpus size, and with `chunk_id` as a tie-break in `ORDER BY`, the
   planner never uses the HNSW index, so `ef_search` has no effect and every dense result
   above is exact search. Phase 3 should fix both before latency is promised.
9. **Per language** (8 to 11 test questions each), e5-large trails BM25 in Portuguese
   (0.752 against 0.850) and leads in German and Russian; indicative only.

Relevance labels come from the drafting sources and an LLM judge over sections pooled from
these same five first-stage strategies, unchanged by the human review: pooled strategies are
slightly favored, and the reranker can only reorder pooled sections.
