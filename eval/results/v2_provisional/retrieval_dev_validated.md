# Retrieval benchmark — split `dev`

29 monolingual answerable questions (31 answerable, 31 in total), top 10 sections per query. Source: `eval/results/v2_provisional/retrieval_dev_validated.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `bm25` | 0.714 | 0.642 | 0.637 | 0.586 | 0.897 | 1.5 | 2.9 |
| `pg_fts` | 0.385 | 0.396 | 0.479 | 0.207 | 0.655 | 16.3 | 25.7 |
| `dense:minilm` | 0.714 | 0.629 | 0.620 | 0.586 | 0.897 | 30.4 | 41.7 |
| `dense:mpnet` | 0.678 | 0.550 | 0.462 | 0.621 | 0.759 | 41.4 | 59.9 |
| `dense:e5-large` | 0.892 | 0.815 | 0.761 | 0.828 | 1.000 | 92.2 | 162.7 |
| `hybrid:e5-large` | 0.845 | 0.788 | 0.749 | 0.759 | 0.966 | 84.5 | 127.6 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `bm25` | 2 | 0.625 | 0.601 | 0.667 | 0.500 |
| `pg_fts` | 2 | 0.500 | 0.500 | 0.500 | 0.500 |
| `dense:minilm` | 2 | 1.000 | 0.910 | 0.833 | 1.000 |
| `dense:mpnet` | 2 | 0.750 | 0.799 | 1.000 | 0.500 |
| `dense:e5-large` | 2 | 0.750 | 0.749 | 0.833 | 0.500 |
| `hybrid:e5-large` | 2 | 1.000 | 0.735 | 0.667 | 1.000 |

## Against `bm25` (paired bootstrap, 95 % CI)

| Strategy | Metric | Δ | 95 % CI | Significant |
|---|---|---|---|---|
| `pg_fts` | mrr | -0.329 | [-0.479, -0.166] | yes |
| `pg_fts` | ndcg@10 | -0.246 | [-0.346, -0.132] | yes |
| `pg_fts` | recall@5 | -0.158 | [-0.299, -0.011] | yes |
| `dense:minilm` | mrr | -0.000 | [-0.189, +0.195] | no |
| `dense:minilm` | ndcg@10 | -0.013 | [-0.136, +0.118] | no |
| `dense:minilm` | recall@5 | -0.017 | [-0.149, +0.109] | no |
| `dense:mpnet` | mrr | -0.036 | [-0.202, +0.133] | no |
| `dense:mpnet` | ndcg@10 | -0.091 | [-0.214, +0.037] | no |
| `dense:mpnet` | recall@5 | -0.175 | [-0.327, -0.030] | yes |
| `dense:e5-large` | mrr | +0.178 | [+0.048, +0.313] | yes |
| `dense:e5-large` | ndcg@10 | +0.173 | [+0.085, +0.273] | yes |
| `dense:e5-large` | recall@5 | +0.123 | [+0.036, +0.226] | yes |
| `hybrid:e5-large` | mrr | +0.131 | [+0.044, +0.223] | yes |
| `hybrid:e5-large` | ndcg@10 | +0.147 | [+0.081, +0.218] | yes |
| `hybrid:e5-large` | recall@5 | +0.112 | [+0.049, +0.184] | yes |
