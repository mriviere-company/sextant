# Retrieval decision — dev split

Sources: `eval/results/retrieval_dev_1_first_stage.json`, `eval/results/retrieval_dev_2_hybrid.json`, `eval/results/retrieval_dev_3_rerank.json`

| Rule | Baseline | Candidate | Δ nDCG@10 | 95 % CI | Threshold | p95 ms | Adopted |
|---|---|---|---|---|---|---|---|
| 1 | `dense:minilm` | `dense:mpnet` | -0.110 | [-0.175, -0.048] | ≥ 0.02 | — | no |
| 1 | `dense:minilm` | `dense:e5-large` | +0.138 | [+0.076, +0.202] | ≥ 0.02 | — | yes |
| 4 | `bm25` | `pg_fts` | -0.302 | [-0.379, -0.225] | ≥ 0.01 | — | no |
| 2 | `dense:e5-large` | `hybrid:e5-large` | +0.011 | [-0.023, +0.044] | ≥ 0.01 | — | no |
| 3 | `dense:e5-large` | `rerank:bge-m3:dense:e5-large` | +0.086 | [+0.050, +0.124] | ≥ 0.03 | 14364 | no |
| 3 | `dense:e5-large` | `rerank:bge-m3@10:dense:e5-large` | +0.048 | [+0.022, +0.079] | ≥ 0.03 | 4097 | no |

**Chosen configuration: `dense:e5-large`**

| Language | n | Loss vs bm25 | Rule 5 applies | Finding |
|---|---|---|---|---|
| de | 11 | -0.211 | no (n < 15) | no |
| en | 12 | -0.088 | no (n < 15) | no |
| es | 12 | +0.032 | no (n < 15) | no |
| fr | 9 | -0.119 | no (n < 15) | no |
| pt | 11 | -0.088 | no (n < 15) | no |
| ru | 11 | +0.072 | no (n < 15) | no |
