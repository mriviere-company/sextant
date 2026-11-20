# Retrieval benchmark — split `dev`

135 monolingual answerable questions (144 answerable, 163 in total), top 10 sections per query. Source: `eval/results/v2_provisional/retrieval_dev_proposed.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `bm25` | 0.651 | 0.636 | 0.683 | 0.496 | 0.844 | 1.4 | 2.7 |
| `pg_fts` | 0.456 | 0.479 | 0.533 | 0.304 | 0.667 | 15.5 | 23.1 |
| `dense:minilm` | 0.644 | 0.600 | 0.618 | 0.511 | 0.822 | 27.1 | 36.7 |
| `dense:mpnet` | 0.571 | 0.519 | 0.500 | 0.452 | 0.726 | 43.6 | 68.6 |
| `dense:e5-large` | 0.832 | 0.791 | 0.803 | 0.748 | 0.963 | 90.0 | 147.6 |
| `hybrid:e5-large` | 0.822 | 0.796 | 0.791 | 0.726 | 0.948 | 91.2 | 152.7 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `bm25` | 9 | 0.250 | 0.197 | 0.170 | 0.222 |
| `pg_fts` | 9 | 0.222 | 0.173 | 0.156 | 0.222 |
| `dense:minilm` | 9 | 0.944 | 0.772 | 0.715 | 0.889 |
| `dense:mpnet` | 9 | 0.744 | 0.686 | 0.644 | 0.667 |
| `dense:e5-large` | 9 | 0.759 | 0.739 | 0.833 | 0.556 |
| `hybrid:e5-large` | 9 | 0.689 | 0.575 | 0.589 | 0.556 |

## Against `bm25` (paired bootstrap, 95 % CI)

| Strategy | Metric | Δ | 95 % CI | Significant |
|---|---|---|---|---|
| `pg_fts` | mrr | -0.194 | [-0.273, -0.113] | yes |
| `pg_fts` | ndcg@10 | -0.157 | [-0.218, -0.095] | yes |
| `pg_fts` | recall@5 | -0.150 | [-0.231, -0.069] | yes |
| `dense:minilm` | mrr | -0.006 | [-0.091, +0.077] | no |
| `dense:minilm` | ndcg@10 | -0.036 | [-0.106, +0.033] | no |
| `dense:minilm` | recall@5 | -0.065 | [-0.141, +0.010] | no |
| `dense:mpnet` | mrr | -0.079 | [-0.169, +0.009] | no |
| `dense:mpnet` | ndcg@10 | -0.117 | [-0.191, -0.044] | yes |
| `dense:mpnet` | recall@5 | -0.183 | [-0.267, -0.101] | yes |
| `dense:e5-large` | mrr | +0.182 | [+0.108, +0.256] | yes |
| `dense:e5-large` | ndcg@10 | +0.154 | [+0.092, +0.216] | yes |
| `dense:e5-large` | recall@5 | +0.120 | [+0.056, +0.185] | yes |
| `hybrid:e5-large` | mrr | +0.172 | [+0.115, +0.227] | yes |
| `hybrid:e5-large` | ndcg@10 | +0.159 | [+0.117, +0.203] | yes |
| `hybrid:e5-large` | recall@5 | +0.107 | [+0.054, +0.164] | yes |
