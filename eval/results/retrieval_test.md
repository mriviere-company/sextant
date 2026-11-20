# Retrieval benchmark — split `test`

57 monolingual answerable questions (65 answerable, 74 in total), top 10 sections per query. Source: `eval/results/retrieval_test.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `bm25` | 0.841 | 0.792 | 0.785 | 0.772 | 0.947 | 1.5 | 2.4 |
| `dense:e5-large` | 0.896 | 0.839 | 0.808 | 0.825 | 0.983 | 221.4 | 655.8 |
| `dense:minilm` | 0.600 | 0.552 | 0.565 | 0.491 | 0.772 | 31.7 | 45.9 |
| `dense:mpnet` | 0.669 | 0.604 | 0.585 | 0.561 | 0.789 | 47.6 | 59.8 |
| `hybrid:e5-large` | 0.917 | 0.865 | 0.827 | 0.877 | 0.965 | 81.8 | 116.2 |
| `pg_fts` | 0.436 | 0.425 | 0.407 | 0.298 | 0.614 | 18.5 | 25.8 |
| `rerank:bge-m3@10:dense:e5-large` | 0.959 | 0.886 | 0.843 | 0.947 | 0.983 | 2125.0 | 4918.5 |
| `rerank:bge-m3:dense:e5-large` | 0.958 | 0.891 | 0.845 | 0.947 | 0.983 | 9311.5 | 16527.4 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `bm25` | 8 | 0.094 | 0.125 | 0.188 | 0.000 |
| `dense:e5-large` | 8 | 0.792 | 0.782 | 0.812 | 0.750 |
| `dense:minilm` | 8 | 0.719 | 0.727 | 0.688 | 0.625 |
| `dense:mpnet` | 8 | 0.549 | 0.606 | 0.750 | 0.250 |
| `hybrid:e5-large` | 8 | 0.662 | 0.705 | 0.812 | 0.500 |
| `pg_fts` | 8 | 0.250 | 0.227 | 0.188 | 0.250 |
| `rerank:bge-m3@10:dense:e5-large` | 8 | 0.812 | 0.802 | 0.844 | 0.750 |
| `rerank:bge-m3:dense:e5-large` | 8 | 0.830 | 0.859 | 0.844 | 0.750 |

## Against `bm25` (paired bootstrap, 95 % CI)

| Strategy | Metric | Δ | 95 % CI | Significant |
|---|---|---|---|---|
| `dense:e5-large` | mrr | +0.056 | [-0.035, +0.149] | no |
| `dense:e5-large` | ndcg@10 | +0.046 | [-0.019, +0.117] | no |
| `dense:e5-large` | recall@5 | +0.023 | [-0.043, +0.093] | no |
| `dense:minilm` | mrr | -0.240 | [-0.362, -0.120] | yes |
| `dense:minilm` | ndcg@10 | -0.240 | [-0.342, -0.140] | yes |
| `dense:minilm` | recall@5 | -0.219 | [-0.331, -0.114] | yes |
| `dense:mpnet` | mrr | -0.172 | [-0.294, -0.054] | yes |
| `dense:mpnet` | ndcg@10 | -0.189 | [-0.291, -0.090] | yes |
| `dense:mpnet` | recall@5 | -0.199 | [-0.308, -0.097] | yes |
| `hybrid:e5-large` | mrr | +0.076 | [+0.024, +0.133] | yes |
| `hybrid:e5-large` | ndcg@10 | +0.073 | [+0.034, +0.115] | yes |
| `hybrid:e5-large` | recall@5 | +0.042 | [-0.014, +0.097] | no |
| `pg_fts` | mrr | -0.405 | [-0.512, -0.299] | yes |
| `pg_fts` | ndcg@10 | -0.367 | [-0.456, -0.280] | yes |
| `pg_fts` | recall@5 | -0.378 | [-0.482, -0.273] | yes |
| `rerank:bge-m3@10:dense:e5-large` | mrr | +0.118 | [+0.042, +0.202] | yes |
| `rerank:bge-m3@10:dense:e5-large` | ndcg@10 | +0.094 | [+0.033, +0.160] | yes |
| `rerank:bge-m3@10:dense:e5-large` | recall@5 | +0.058 | [-0.006, +0.124] | no |
| `rerank:bge-m3:dense:e5-large` | mrr | +0.117 | [+0.040, +0.201] | yes |
| `rerank:bge-m3:dense:e5-large` | ndcg@10 | +0.099 | [+0.041, +0.163] | yes |
| `rerank:bge-m3:dense:e5-large` | recall@5 | +0.060 | [-0.004, +0.124] | no |
