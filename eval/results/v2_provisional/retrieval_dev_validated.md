# Retrieval benchmark — split `dev`

54 monolingual answerable questions (58 answerable, 58 in total), top 10 sections per query. Source: `eval/results/v2_provisional/retrieval_dev_validated.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `bm25` | 0.695 | 0.652 | 0.685 | 0.537 | 0.907 | 1.3 | 2.7 |
| `pg_fts` | 0.421 | 0.422 | 0.496 | 0.241 | 0.685 | 12.8 | 19.4 |
| `dense:minilm` | 0.743 | 0.628 | 0.611 | 0.630 | 0.889 | 18.9 | 29.1 |
| `dense:mpnet` | 0.631 | 0.547 | 0.519 | 0.518 | 0.815 | 47.7 | 88.2 |
| `dense:e5-large` | 0.858 | 0.782 | 0.774 | 0.778 | 0.982 | 498.5 | 2392.2 |
| `hybrid:e5-large` | 0.843 | 0.783 | 0.734 | 0.759 | 0.963 | 77.8 | 159.8 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `bm25` | 4 | 0.312 | 0.300 | 0.333 | 0.250 |
| `pg_fts` | 4 | 0.250 | 0.250 | 0.250 | 0.250 |
| `dense:minilm` | 4 | 1.000 | 0.955 | 0.917 | 1.000 |
| `dense:mpnet` | 4 | 0.625 | 0.650 | 0.750 | 0.500 |
| `dense:e5-large` | 4 | 0.625 | 0.690 | 0.917 | 0.250 |
| `hybrid:e5-large` | 4 | 0.625 | 0.525 | 0.583 | 0.500 |

## Against `bm25` (paired bootstrap, 95 % CI)

| Strategy | Metric | Δ | 95 % CI | Significant |
|---|---|---|---|---|
| `pg_fts` | mrr | -0.274 | [-0.394, -0.153] | yes |
| `pg_fts` | ndcg@10 | -0.230 | [-0.307, -0.149] | yes |
| `pg_fts` | recall@5 | -0.190 | [-0.298, -0.087] | yes |
| `dense:minilm` | mrr | +0.048 | [-0.082, +0.182] | no |
| `dense:minilm` | ndcg@10 | -0.024 | [-0.119, +0.075] | no |
| `dense:minilm` | recall@5 | -0.074 | [-0.175, +0.024] | no |
| `dense:mpnet` | mrr | -0.063 | [-0.198, +0.076] | no |
| `dense:mpnet` | ndcg@10 | -0.105 | [-0.209, +0.002] | no |
| `dense:mpnet` | recall@5 | -0.166 | [-0.274, -0.065] | yes |
| `dense:e5-large` | mrr | +0.163 | [+0.048, +0.278] | yes |
| `dense:e5-large` | ndcg@10 | +0.131 | [+0.039, +0.223] | yes |
| `dense:e5-large` | recall@5 | +0.089 | [+0.006, +0.173] | yes |
| `hybrid:e5-large` | mrr | +0.148 | [+0.071, +0.225] | yes |
| `hybrid:e5-large` | ndcg@10 | +0.131 | [+0.071, +0.190] | yes |
| `hybrid:e5-large` | recall@5 | +0.049 | [-0.022, +0.115] | no |
