# Retrieval benchmark — split `dev`

66 monolingual answerable questions (71 answerable, 84 in total), top 10 sections per query. Source: `eval/results/retrieval_dev_1_first_stage.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `bm25` | 0.859 | 0.758 | 0.721 | 0.788 | 0.939 | 1.4 | 2.9 |
| `pg_fts` | 0.443 | 0.456 | 0.497 | 0.288 | 0.667 | 20.8 | 31.0 |
| `dense:minilm` | 0.784 | 0.685 | 0.674 | 0.682 | 0.939 | 26.2 | 43.5 |
| `dense:mpnet` | 0.628 | 0.575 | 0.606 | 0.470 | 0.833 | 39.4 | 100.5 |
| `dense:e5-large` | 0.902 | 0.823 | 0.764 | 0.849 | 0.970 | 439.7 | 1454.7 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `bm25` | 5 | 0.400 | 0.342 | 0.300 | 0.400 |
| `pg_fts` | 5 | 0.200 | 0.078 | 0.050 | 0.200 |
| `dense:minilm` | 5 | 0.867 | 0.823 | 0.843 | 0.800 |
| `dense:mpnet` | 5 | 0.640 | 0.667 | 0.527 | 0.600 |
| `dense:e5-large` | 5 | 0.767 | 0.804 | 0.883 | 0.600 |

## Against `bm25` (paired bootstrap, 95 % CI)

| Strategy | Metric | Δ | 95 % CI | Significant |
|---|---|---|---|---|
| `pg_fts` | mrr | -0.415 | [-0.516, -0.313] | yes |
| `pg_fts` | ndcg@10 | -0.302 | [-0.379, -0.225] | yes |
| `pg_fts` | recall@5 | -0.225 | [-0.329, -0.122] | yes |
| `dense:minilm` | mrr | -0.074 | [-0.178, +0.029] | no |
| `dense:minilm` | ndcg@10 | -0.073 | [-0.153, +0.007] | no |
| `dense:minilm` | recall@5 | -0.048 | [-0.123, +0.031] | no |
| `dense:mpnet` | mrr | -0.231 | [-0.339, -0.122] | yes |
| `dense:mpnet` | ndcg@10 | -0.183 | [-0.271, -0.096] | yes |
| `dense:mpnet` | recall@5 | -0.115 | [-0.207, -0.029] | yes |
| `dense:e5-large` | mrr | +0.043 | [-0.037, +0.125] | no |
| `dense:e5-large` | ndcg@10 | +0.064 | [+0.001, +0.133] | yes |
| `dense:e5-large` | recall@5 | +0.043 | [-0.022, +0.117] | no |
